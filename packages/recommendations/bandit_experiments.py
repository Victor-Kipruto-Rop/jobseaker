"""Deterministic experiment assignment and bias-aware ranking evaluation."""
from __future__ import annotations
import hashlib
import hmac
import math
from collections import defaultdict
from typing import Iterable

VALID_EVENTS = {"impression", "click", "save", "apply", "interview", "offer", "dismiss"}

def assign_arm(user_id: int, experiment_id: str, arms: list[str], secret: str) -> dict:
    if user_id <= 0 or not experiment_id or len(experiment_id) > 100:
        raise ValueError("Valid user and experiment identifiers are required")
    normalized = list(dict.fromkeys(str(a) for a in arms if a))
    if len(normalized) < 2 or len(normalized) > 8 or not secret:
        raise ValueError("Provide 2..8 arms and a non-empty assignment secret")
    digest = hmac.new(secret.encode(), f"{experiment_id}:{user_id}".encode(),
                      hashlib.sha256).digest()
    bucket = int.from_bytes(digest[:8], "big") / (2**64)
    index = min(int(bucket * len(normalized)), len(normalized) - 1)
    return {"experiment_id": experiment_id, "arm": normalized[index],
            "propensity": 1.0 / len(normalized), "assignment_bucket": round(bucket, 12),
            "assignment_unit": "candidate", "stable": True}

def _wilson(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total <= 0:
        return 0.0, 0.0
    p = successes / total
    denominator = 1 + z*z/total
    center = (p + z*z/(2*total))/denominator
    margin = z*math.sqrt((p*(1-p)+z*z/(4*total))/total)/denominator
    return max(0.0, center-margin), min(1.0, center+margin)

def evaluate_experiment(events: Iterable[dict], arms: list[str], min_impressions: int = 100) -> dict:
    stats = defaultdict(lambda: {"impressions": 0, "clicks": 0, "saves": 0,
                                 "applies": 0, "interviews": 0, "offers": 0,
                                 "dismissals": 0, "weighted_reward": 0.0})
    for event in events:
        arm = str(event.get("recommendation_source") or event.get("arm") or "")
        kind = str(event.get("event_type") or "")
        if arm not in arms or kind not in VALID_EVENTS:
            continue
        row = stats[arm]
        if kind == "impression":
            row["impressions"] += 1
        elif kind == "click":
            row["clicks"] += 1; row["weighted_reward"] += 0.25
        elif kind == "save":
            row["saves"] += 1; row["weighted_reward"] += 1.0
        elif kind == "apply":
            row["applies"] += 1; row["weighted_reward"] += 3.0
        elif kind == "interview":
            row["interviews"] += 1; row["weighted_reward"] += 5.0
        elif kind == "offer":
            row["offers"] += 1; row["weighted_reward"] += 7.0
        elif kind == "dismiss":
            row["dismissals"] += 1; row["weighted_reward"] -= 1.0
    report = {}
    for arm in arms:
        row = dict(stats[arm])
        n = row["impressions"]
        row["ctr"] = row["clicks"] / n if n else None
        row["apply_rate"] = row["applies"] / n if n else None
        row["reward_per_impression"] = row["weighted_reward"] / n if n else None
        row["ctr_wilson_95"] = list(_wilson(row["clicks"], n))
        row["eligible_for_decision"] = n >= min_impressions
        report[arm] = row
    eligible = [name for name in arms if report[name]["eligible_for_decision"]]
    winner = max(eligible, key=lambda name: report[name]["reward_per_impression"] or 0) if eligible else None
    return {"arms": report, "minimum_impressions": min_impressions,
            "decision": "candidate_winner" if winner else "insufficient_exposure",
            "candidate_winner": winner,
            "automatic_promotion": False,
            "note": "Observational experiment metrics; require candidate-level holdout and guardrail review before rollout."}
