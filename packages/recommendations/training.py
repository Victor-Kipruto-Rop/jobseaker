"""Offline LightGBM learning-to-rank training and controlled model promotion."""
from __future__ import annotations

import hashlib
import math
import pickle
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database.models.career import RecommendationInteraction, RecommendationModel
from packages.recommendations.engine import FEATURE_NAMES
from packages.storage.objects import read_private_object, store_private_object

# Graded relevance labels; dismissals/skips are explicit non-relevance signals.
RELEVANCE = {"offer": 4, "interview": 3, "apply": 2, "save": 1,
             "dismiss": 0, "skip": 0}
FEATURE_SCHEMA_VERSION = 1


def _auc(labels: list[int], scores: list[float]) -> float | None:
    positives = sum(labels)
    negatives = len(labels) - positives
    if not positives or not negatives:
        return None
    ordered = sorted(zip(scores, labels), key=lambda item: item[0])
    rank_sum = 0.0
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][0] == ordered[index][0]:
            end += 1
        average_rank = ((index + 1) + end) / 2.0
        rank_sum += average_rank * sum(label for _, label in ordered[index:end])
        index = end
    return (rank_sum - positives * (positives + 1) / 2.0) / (positives * negatives)


def _dcg(labels: list[int]) -> float:
    return sum((2 ** label - 1) / math.log2(index + 2)
               for index, label in enumerate(labels))


def _group_ndcg(labels: list[int], scores: list[float], k: int = 10) -> float | None:
    if not labels or not any(labels):
        return None
    ranked = [label for _, label in sorted(zip(scores, labels), reverse=True)[:k]]
    ideal = sorted(labels, reverse=True)[:k]
    denominator = _dcg(ideal)
    return _dcg(ranked) / denominator if denominator else None


def _grouped_samples(rows) -> list[dict[str, Any]]:
    # One candidate/job pair per query group. Keep the strongest observed label
    # and its corresponding feature snapshot to avoid counting repeat clicks as
    # independent training examples.
    pairs: dict[tuple[int, str], dict[str, Any]] = {}
    for row in rows:
        features = row.feature_snapshot if isinstance(row.feature_snapshot, dict) else {}
        if not features or not row.item_key or row.event_type not in RELEVANCE:
            continue
        label = RELEVANCE[row.event_type]
        key = (row.user_id, row.item_key)
        current = pairs.get(key)
        if current is None or label > current["label"] or (
            label == current["label"] and row.created_at > current["created_at"]
        ):
            pairs[key] = {
                "user_id": row.user_id, "item_key": row.item_key,
                "label": label, "created_at": row.created_at,
                "features": {name: float(features.get(name, 0.0) or 0.0)
                             for name in FEATURE_NAMES},
            }
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for sample in pairs.values():
        grouped[sample["user_id"]].append(sample)
    return [
        {"user_id": user_id, "samples": sorted(items, key=lambda x: x["item_key"])}
        for user_id, items in sorted(grouped.items())
        if len(items) >= 2 and len({item["label"] for item in items}) > 1
    ]


def _flatten(groups: list[dict[str, Any]]):
    samples = [sample for group in groups for sample in group["samples"]]
    matrix = [
        [sample["features"][name] for name in FEATURE_NAMES] for sample in samples
    ]
    labels = [sample["label"] for sample in samples]
    sizes = [len(group["samples"]) for group in groups]
    return matrix, labels, sizes


def train_and_register_ranker(db: Session, *, min_rows: int = 100) -> dict[str, Any]:
    """Train a LambdaRank model with candidate-level query groups and user holdout."""
    rows = db.scalars(select(RecommendationInteraction).where(
        RecommendationInteraction.event_type.in_(tuple(RELEVANCE))
    ).order_by(RecommendationInteraction.created_at.asc()).limit(200000)).all()
    groups = _grouped_samples(rows)
    total_rows = sum(len(group["samples"]) for group in groups)
    if total_rows < min_rows:
        return {"status": "insufficient_data", "rows": total_rows,
                "required_rows": min_rows, "query_groups": len(groups)}
    if len(groups) < 5:
        return {"status": "insufficient_query_groups", "rows": total_rows,
                "query_groups": len(groups), "required_groups": 5}

    # Split by candidate, not by individual events, to avoid candidate leakage.
    ordered = sorted(groups, key=lambda group: hashlib.sha256(
        str(group["user_id"]).encode()
    ).hexdigest())
    split = max(1, min(len(ordered) - 1, int(len(ordered) * 0.8)))
    train_groups, validation_groups = ordered[:split], ordered[split:]
    if not train_groups or not validation_groups:
        return {"status": "insufficient_validation_groups", "rows": total_rows}
    x_train, y_train, group_train = _flatten(train_groups)
    x_valid, y_valid, group_valid = _flatten(validation_groups)
    if len(set(y_train)) < 2 or len(set(y_valid)) < 2:
        return {"status": "insufficient_class_balance", "rows": total_rows,
                "training_labels": sorted(set(y_train)),
                "validation_labels": sorted(set(y_valid))}

    try:
        from lightgbm import LGBMRanker
    except ImportError as exc:
        raise RuntimeError('Install optional ML dependencies with pip install -e ".[ml]"') from exc

    model = LGBMRanker(
        objective="lambdarank", metric="ndcg", eval_at=[10],
        n_estimators=240, max_depth=6, num_leaves=23,
        learning_rate=0.035, verbosity=-1, random_state=17,
        label_gain=[0, 1, 3, 7, 15],
    )
    model.fit(
        x_train, y_train, group=group_train,
        eval_set=[(x_valid, y_valid)], eval_group=[group_valid],
        eval_at=[10], callbacks=[],
    )
    scores = [float(value) for value in model.predict(x_valid)]
    binary_labels = [int(value > 0) for value in y_valid]
    offset = 0
    ndcg_values = []
    for size in group_valid:
        metric = _group_ndcg(y_valid[offset:offset + size], scores[offset:offset + size])
        if metric is not None:
            ndcg_values.append(metric)
        offset += size
    metrics = {
        "validation_auc": _auc(binary_labels, scores),
        "validation_ndcg_at_10": (
            sum(ndcg_values) / len(ndcg_values) if ndcg_values else None
        ),
        "validation_rows": len(y_valid),
        "validation_query_groups": len(validation_groups),
        "training_query_groups": len(train_groups),
        "training_rows": len(y_train),
        "feature_names": list(FEATURE_NAMES),
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "evaluation": "candidate_group_holdout_lambdarank",
    }
    if metrics["validation_auc"] is None or metrics["validation_ndcg_at_10"] is None:
        return {"status": "invalid_validation_metrics", "rows": total_rows,
                "metrics": metrics}

    artifact = pickle.dumps(model, protocol=pickle.HIGHEST_PROTOCOL)
    digest = hashlib.sha256(artifact).hexdigest()
    stored = store_private_object(
        artifact, "lightgbm-lambdarank.pkl", "application/octet-stream",
        owner_scope="recommendation-models",
    )
    trained_at = datetime.now(timezone.utc)
    version = trained_at.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    record = RecommendationModel(
        model_name="job-relevance-ltr", model_version=version,
        algorithm="lightgbm_lambdarank", artifact_key=stored["object_key"],
        artifact_sha256=digest, feature_schema_version=FEATURE_SCHEMA_VERSION,
        training_rows=total_rows, metrics=metrics, status="candidate",
        trained_at=trained_at,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"status": "candidate_registered", "model_id": record.id,
            "model_version": version, "training_rows": total_rows,
            "metrics": metrics, "promotion_required": True}


def promote_ranker(
    db: Session, model_id: int, *, minimum_auc: float = 0.60,
    minimum_ndcg: float = 0.45,
) -> RecommendationModel:
    """Promote only a candidate that passes both relevance and ranking-quality gates."""
    candidate = db.scalar(select(RecommendationModel).where(
        RecommendationModel.id == model_id
    ).with_for_update())
    if candidate is None:
        raise LookupError("Recommendation model not found")
    metrics = candidate.metrics or {}
    auc = metrics.get("validation_auc")
    ndcg = metrics.get("validation_ndcg_at_10")
    if (candidate.status != "candidate" or candidate.algorithm != "lightgbm_lambdarank"
            or auc is None or ndcg is None or float(auc) < minimum_auc
            or float(ndcg) < minimum_ndcg):
        raise ValueError("Model does not meet the active LTR promotion gates")
    now = datetime.now(timezone.utc)
    active = db.scalars(select(RecommendationModel).where(
        RecommendationModel.model_name == candidate.model_name,
        RecommendationModel.status == "active",
    ).with_for_update()).all()
    for previous in active:
        previous.status = "retired"
    candidate.status = "active"
    candidate.promoted_at = now
    db.commit()
    db.refresh(candidate)
    return candidate


def load_active_ranker(db: Session):
    """Load an integrity-checked, trusted LTR artifact from private object storage."""
    row = db.scalar(select(RecommendationModel).where(
        RecommendationModel.model_name == "job-relevance-ltr",
        RecommendationModel.status == "active",
    ).order_by(RecommendationModel.promoted_at.desc()))
    if row is None:
        return None
    if row.algorithm != "lightgbm_lambdarank":
        raise RuntimeError("Active recommendation model is not a supported LTR artifact")
    artifact = read_private_object(row.artifact_key)
    if hashlib.sha256(artifact).hexdigest() != row.artifact_sha256:
        raise RuntimeError("Registered model artifact integrity check failed")
    model = pickle.loads(artifact)  # Only trusted, application-written private artifacts.
    if list(getattr(model, "feature_name_", [])) != list(FEATURE_NAMES):
        raise RuntimeError("Registered model feature schema is incompatible")
    return model
