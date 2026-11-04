"""Transactional outbox writer and retryable Kafka relay."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session
from packages.database.models.career import EventOutbox
from uuid import uuid4

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 8
BATCH_SIZE = 100


def enqueue_event(
    db: Session, topic: str, payload: dict[str, Any], *,
    partition_key: str = "", event_id: str | None = None,
    producer: str = "jobseeker-api", schema_version: int = 1,
) -> str:
    """Add an event to the caller's transaction. The caller owns commit/rollback."""
    from packages.events.kafka import ALLOWED_TOPICS
    if topic not in ALLOWED_TOPICS:
        raise ValueError(f"Unsupported JobSeeker event topic: {topic}")
    identifier = event_id or str(uuid4())
    now = datetime.now(timezone.utc)
    envelope = {
        "event_id": identifier, "event_type": topic, "schema_version": schema_version,
        "occurred_at": now.isoformat(), "producer": producer, "data": payload,
    }
    db.add(EventOutbox(
        event_id=identifier, topic=topic, partition_key=partition_key,
        envelope=envelope, status="pending", attempts=0,
        available_at=now, created_at=now,
    ))
    return identifier


async def relay_outbox_batch(
    session_factory: Callable[[], Session], producer: Any, *,
    batch_size: int = BATCH_SIZE, max_attempts: int = MAX_ATTEMPTS,
) -> dict[str, int]:
    """Claim a batch, publish stable event IDs, and persist retry/DLQ outcomes.

    Delivery is at-least-once: a process crash after Kafka ack but before the
    database update can cause a duplicate. Consumers must use EventInbox.
    """
    now = datetime.now(timezone.utc)
    stale_lock = now - timedelta(minutes=5)
    eligible = or_(
        and_(EventOutbox.status.in_(("pending", "retry")), EventOutbox.available_at <= now),
        and_(EventOutbox.status == "processing", EventOutbox.locked_at < stale_lock),
    )
    with session_factory() as db:
        query = (select(EventOutbox)
                 .where(eligible)
                 .order_by(EventOutbox.created_at)
                 .limit(max(1, min(batch_size, 500)))
                 .with_for_update(skip_locked=True))
        rows = list(db.scalars(query).all())
        ids = [row.id for row in rows]
        for row in rows:
            row.status = "processing"
            row.locked_at = now
        db.commit()

    result = {"published": 0, "retrying": 0, "dead_lettered": 0}
    for row_id in ids:
        with session_factory() as db:
            row = db.get(EventOutbox, row_id)
            if row is None or row.status != "processing":
                continue
            topic, envelope, key = row.topic, row.envelope, row.partition_key
            try:
                await producer.send_and_wait(
                    topic, envelope, key=key.encode("utf-8") if key else None,
                )
                row.status = "published"
                row.published_at = datetime.now(timezone.utc)
                row.locked_at = None
                row.last_error = ""
                result["published"] += 1
            except Exception as exc:
                row.attempts += 1
                row.last_error = str(exc)[:2000]
                row.locked_at = None
                if row.attempts >= max_attempts:
                    # Do not mark terminal until the broker acknowledges the DLQ record.
                    try:
                        await producer.send_and_wait(
                            f"{topic}.dlq",
                            {"original_topic": topic, "event": envelope,
                             "error": row.last_error, "attempts": row.attempts},
                            key=key.encode("utf-8") if key else None,
                        )
                        row.status = "dead_letter"
                        result["dead_lettered"] += 1
                    except Exception as dlq_exc:
                        row.status = "retry"
                        row.available_at = datetime.now(timezone.utc) + timedelta(minutes=5)
                        row.last_error = (row.last_error + " | DLQ publish failed: " +
                                          str(dlq_exc))[:2000]
                        logger.exception("Could not publish event to DLQ; retaining outbox row",
                                         extra={"event_id": row.event_id})
                        result["retrying"] += 1
                else:
                    delay = min(3600, 2 ** min(row.attempts, 11))
                    row.status = "retry"
                    row.available_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
                    result["retrying"] += 1
            db.commit()
    return result


async def run_outbox_relay(
    session_factory: Callable[[], Session], producer_factory: Callable[[], Any], *,
    poll_seconds: float = 1.0, stop: asyncio.Event | None = None,
) -> None:
    """Long-running worker loop; lifecycle/health are owned by the process runner."""
    producer = producer_factory()
    await producer.start()
    try:
        while stop is None or not stop.is_set():
            outcome = await relay_outbox_batch(session_factory, producer)
            if not outcome["published"] and not outcome["retrying"] and not outcome["dead_lettered"]:
                await asyncio.sleep(max(0.1, poll_seconds))
    finally:
        await producer.stop()
