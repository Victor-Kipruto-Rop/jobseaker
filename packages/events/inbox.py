"""Replay-safe consumer transaction helper."""
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from packages.database.models.career import EventInbox
from packages.events.contracts import EventEnvelope


def consume_once(
    db: Session, consumer_name: str, envelope: dict, handler,
) -> tuple[bool, dict]:
    """Run handler once per consumer/event in the same transaction.

    Handler must perform only database work in this transaction. External side
    effects must be emitted through the outbox, never called inline.
    """
    if not consumer_name or len(consumer_name) > 120:
        raise ValueError("consumer_name must contain 1..120 characters")
    validated = EventEnvelope.model_validate(envelope)
    event_id = validated.event_id
    existing = db.scalar(select(EventInbox).where(
        EventInbox.consumer_name == consumer_name, EventInbox.event_id == event_id,
    ))
    if existing:
        return False, existing.result or {}
    try:
        result = handler(db, envelope) or {}
    except Exception:
        db.rollback()
        raise
    db.add(EventInbox(
        consumer_name=consumer_name, event_id=event_id,
        processed_at=datetime.now(timezone.utc), result=result,
    ))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(EventInbox).where(
            EventInbox.consumer_name == consumer_name, EventInbox.event_id == event_id,
        ))
        if existing:
            return False, existing.result or {}
        raise
    return True, result
