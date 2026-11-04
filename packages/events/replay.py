"""Explicit, bounded replay of already-published outbox events."""
from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.orm import Session
from packages.database.models.career import EventOutbox
from packages.events.schema_registry import validate_envelope

async def replay_published_events(db: Session, producer, *, topic: str,
                            event_ids: list[str], confirm: bool = False) -> dict:
    if not confirm:
        raise PermissionError("Replay requires explicit operator confirmation")
    if not topic or len(event_ids) == 0 or len(event_ids) > 100:
        raise ValueError("Replay requires a topic and 1..100 event IDs")
    rows = db.scalars(select(EventOutbox).where(
        EventOutbox.topic == topic,
        EventOutbox.event_id.in_(list(dict.fromkeys(event_ids))),
        EventOutbox.status == "published",
    ).order_by(EventOutbox.created_at)).all()
    published, errors = [], []
    for row in rows:
        validate_envelope(row.envelope)
        try:
            await producer.send_and_wait(topic, row.envelope,
                key=row.partition_key.encode() if row.partition_key else None)
            published.append(row.event_id)
        except Exception as exc:
            errors.append({"event_id": row.event_id, "error": str(exc)[:500]})
    return {"topic": topic, "requested": len(set(event_ids)),
            "found": len(rows), "replayed": published, "errors": errors,
            "original_event_ids_preserved": True,
            "consumer_deduplication_note": "Use a new consumer_name for intentional reprocessing; existing inbox receipts suppress duplicates."}
