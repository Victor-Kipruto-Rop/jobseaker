from datetime import datetime, timezone
from types import SimpleNamespace

from packages.recommendations.engine import FEATURE_NAMES
from packages.recommendations.training import _group_ndcg, _grouped_samples


def interaction(user_id, item_key, event_type, features):
    return SimpleNamespace(
        user_id=user_id, item_key=item_key, event_type=event_type,
        feature_snapshot=features, created_at=datetime.now(timezone.utc),
    )


def test_training_samples_are_grouped_by_candidate_and_job():
    features = {name: 0.2 for name in FEATURE_NAMES}
    rows = [
        interaction(1, "job-a", "save", features),
        interaction(1, "job-a", "apply", {**features, "skill_overlap": 0.9}),
        interaction(1, "job-b", "dismiss", features),
        interaction(2, "job-c", "offer", features),
        interaction(2, "job-d", "skip", features),
    ]
    groups = _grouped_samples(rows)
    first = next(group for group in groups if group["user_id"] == 1)
    job_a = next(item for item in first["samples"] if item["item_key"] == "job-a")
    assert job_a["label"] == 2
    assert job_a["features"]["skill_overlap"] == 0.9
    assert len(first["samples"]) == 2


def test_group_ndcg_rewards_correct_ordering():
    labels = [4, 0, 2]
    assert _group_ndcg(labels, [3.0, 1.0, 2.0]) == 1.0
    assert _group_ndcg(labels, [0.0, 3.0, 1.0]) < 1.0
