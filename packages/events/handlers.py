"""Database-only handlers for durable candidate activity and inbox events."""
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from packages.database.models.career import CandidatePreferenceState, Notification

POSITIVE = {"click": 0.35, "save": 1.0, "apply": 1.0, "interview": 1.0, "offer": 1.0}
NEGATIVE = {"dismiss": -1.0, "skip": -0.35}


def handle_user_activity(db: Session, envelope: dict) -> dict:
    data = envelope.get("data") or {}
    user_id = data.get("user_id")
    if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
        raise ValueError("user.activity requires a valid user_id")
    kind = str(data.get("event_type") or "")
    reward = POSITIVE.get(kind, NEGATIVE.get(kind, 0.0))
    features = data.get("feature_snapshot") or {}
    if not reward or not isinstance(features, dict) or not features:
        return {"preference_updated": False, "reason": "no_numeric_preference_signal"}
    state = db.scalar(select(CandidatePreferenceState).where(
        CandidatePreferenceState.user_id == user_id,
    ).with_for_update())
    if state is None:
        state = CandidatePreferenceState(
            user_id=user_id, preference_vector={}, interaction_count=0,
            updated_at=datetime.now(timezone.utc),
        )
        db.add(state)
        db.flush()
    vector = dict(state.preference_vector or {})
    for name, raw in features.items():
        if not isinstance(name, str) or len(name) > 80:
            continue
        try:
            value = max(-1.0, min(1.0, float(raw)))
        except (TypeError, ValueError):
            continue
        previous = float(vector.get(name, 0.0) or 0.0)
        vector[name] = round(max(-1.0, min(1.0, previous * 0.90 + value * reward * 0.10)), 6)
    state.preference_vector = dict(sorted(
        vector.items(), key=lambda item: abs(item[1]), reverse=True,
    )[:64])
    state.interaction_count = int(state.interaction_count or 0) + 1
    state.updated_at = datetime.now(timezone.utc)
    return {"preference_updated": True, "interaction_count": state.interaction_count}


def handle_email_classified(db: Session, envelope: dict) -> dict:
    data = envelope.get("data") or {}
    user_id = data.get("user_id")
    if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
        raise ValueError("email.classified requires a valid user_id")
    if not data.get("action_required"):
        return {"notification_created": False}
    classification = str(data.get("classification") or "Recruiter update")[:80]
    message_id = data.get("email_message_id")
    db.add(Notification(
        user_id=user_id,
        title="Recruiter email needs review",
        body=f"{classification.replace('_', ' ').title()}. Open your inbox to review the suggested next step.",
        created_at=datetime.now(timezone.utc),
    ))
    return {"notification_created": True, "email_message_id": message_id}
