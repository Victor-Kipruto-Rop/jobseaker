"""Offline ranking-model training, evaluation and controlled registry promotion."""
from __future__ import annotations

import hashlib
import pickle
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database.models.career import RecommendationInteraction, RecommendationModel
from packages.recommendations.engine import FEATURE_NAMES
from packages.storage.objects import read_private_object, store_private_object

POSITIVE_LABELS = {"save", "apply", "interview", "offer"}
NEGATIVE_LABELS = {"dismiss", "skip"}
FEATURE_SCHEMA_VERSION = 1


def _auc(labels: list[int], scores: list[float]) -> float | None:
    positives = [score for label, score in zip(labels, scores) if label == 1]
    negatives = [score for label, score in zip(labels, scores) if label == 0]
    if not positives or not negatives:
        return None
    comparisons = sum(1.0 if p > n else 0.5 if p == n else 0.0
                      for p in positives for n in negatives)
    return comparisons / (len(positives) * len(negatives))


def _ndcg_at_k(labels: list[int], scores: list[float], k: int = 10) -> float | None:
    if not labels or not any(labels):
        return None
    ranked = sorted(zip(scores, labels), reverse=True)[:k]
    ideal = sorted(labels, reverse=True)[:k]
    def dcg(values):
        return sum(label / __import__("math").log2(index + 2)
                   for index, label in enumerate(values))
    denominator = dcg(ideal)
    return dcg([label for _, label in ranked]) / denominator if denominator else None


def train_and_register_ranker(db: Session, *, min_rows: int = 100) -> dict[str, Any]:
    """Train on explicit positive/negative feedback and save an unelevated candidate."""
    rows = db.scalars(select(RecommendationInteraction).where(
        RecommendationInteraction.event_type.in_(tuple(POSITIVE_LABELS | NEGATIVE_LABELS))
    ).order_by(RecommendationInteraction.created_at.asc()).limit(100000)).all()
    samples = []
    for row in rows:
        features = row.feature_snapshot if isinstance(row.feature_snapshot, dict) else {}
        if not features:
            continue
        samples.append({
            "created_at": row.created_at,
            "label": int(row.event_type in POSITIVE_LABELS),
            "features": {name: float(features.get(name, 0.0) or 0.0) for name in FEATURE_NAMES},
        })
    if len(samples) < min_rows:
        return {"status": "insufficient_data", "rows": len(samples), "required_rows": min_rows}
    labels = [item["label"] for item in samples]
    if sum(labels) < 10 or len(labels) - sum(labels) < 10:
        return {"status": "insufficient_class_balance", "rows": len(samples),
                "positive": sum(labels), "negative": len(labels) - sum(labels)}

    split = max(int(len(samples) * 0.8), 1)
    train, validation = samples[:split], samples[split:]
    if not validation:
        return {"status": "insufficient_validation_data", "rows": len(samples)}
    y_train = [item["label"] for item in train]
    if len(set(y_train)) < 2:
        return {"status": "single_class_training_window", "rows": len(samples)}
    try:
        from lightgbm import LGBMClassifier
    except ImportError as exc:
        raise RuntimeError('Install the optional ML dependencies with pip install -e ".[ml]"') from exc

    model = LGBMClassifier(
        objective="binary", n_estimators=160, max_depth=5, num_leaves=23,
        learning_rate=0.035, verbosity=-1, class_weight="balanced",
        random_state=17,
    )
    x_train = [[item["features"][name] for name in FEATURE_NAMES] for item in train]
    x_valid = [[item["features"][name] for name in FEATURE_NAMES] for item in validation]
    y_valid = [item["label"] for item in validation]
    model.fit(pd.DataFrame(x_train, columns=FEATURE_NAMES), y_train)
    scores = [float(value) for value in model.predict_proba(
        pd.DataFrame(x_valid, columns=FEATURE_NAMES)
    )[:, 1]]
    metrics = {
        "validation_auc": _auc(y_valid, scores),
        "validation_ndcg_at_10": _ndcg_at_k(y_valid, scores),
        "validation_rows": len(validation),
        "validation_positive_rate": round(sum(y_valid) / len(y_valid), 4),
        "feature_names": list(FEATURE_NAMES),
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "evaluation": "chronological_holdout",
    }
    if metrics["validation_auc"] is None:
        return {"status": "invalid_validation_split", "rows": len(samples), "metrics": metrics}

    artifact = pickle.dumps(model, protocol=pickle.HIGHEST_PROTOCOL)
    digest = hashlib.sha256(artifact).hexdigest()
    stored = store_private_object(
        artifact, "lightgbm-ranker.pkl", "application/octet-stream",
        owner_scope="recommendation-models",
    )
    trained_at = datetime.now(timezone.utc)
    version = trained_at.strftime("%Y%m%dT%H%M%SZ")
    record = RecommendationModel(
        model_name="job-relevance-ltr", model_version=version,
        algorithm="lightgbm_binary_classifier", artifact_key=stored["object_key"],
        artifact_sha256=digest, feature_schema_version=FEATURE_SCHEMA_VERSION,
        training_rows=len(samples), metrics=metrics, status="candidate",
        trained_at=trained_at,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"status": "candidate_registered", "model_id": record.id,
            "model_version": version, "training_rows": len(samples),
            "metrics": metrics, "promotion_required": True}


def promote_ranker(db: Session, model_id: int, *, minimum_auc: float = 0.60) -> RecommendationModel:
    """Promote only a sufficiently evaluated candidate; never auto-promote training output."""
    candidate = db.scalar(select(RecommendationModel).where(
        RecommendationModel.id == model_id
    ).with_for_update())
    if candidate is None:
        raise LookupError("Recommendation model not found")
    auc = (candidate.metrics or {}).get("validation_auc")
    if candidate.status != "candidate" or auc is None or float(auc) < minimum_auc:
        raise ValueError("Model does not meet the active-model promotion gate")
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
    """Load the active, integrity-checked model from private object storage."""
    row = db.scalar(select(RecommendationModel).where(
        RecommendationModel.model_name == "job-relevance-ltr",
        RecommendationModel.status == "active",
    ).order_by(RecommendationModel.promoted_at.desc()))
    if row is None:
        return None
    artifact = read_private_object(row.artifact_key)
    if hashlib.sha256(artifact).hexdigest() != row.artifact_sha256:
        raise RuntimeError("Registered model artifact integrity check failed")
    model = pickle.loads(artifact)  # Only trusted, application-written private artifacts.
    if list(getattr(model, "feature_name_", [])) and list(model.feature_name_) != list(FEATURE_NAMES):
        raise RuntimeError("Registered model feature schema is incompatible")
    return model
