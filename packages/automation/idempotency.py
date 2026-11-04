"""Database-backed application dispatch idempotency."""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from packages.database.models.career import ApplicationDispatchKey


class DispatchConflict(ValueError):
    pass


def reserve_application_dispatch(
    db: Session, *, user_id: int, application_id: int, idempotency_key: str,
    payload: dict,
) -> ApplicationDispatchKey:
    if not idempotency_key or len(idempotency_key) > 128:
        raise ValueError("An idempotency key of 1..128 characters is required")
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    raw_job_key = str(payload.get("job_key") or payload.get("job_url") or f"application:{application_id}")
    job_key = hashlib.sha256(raw_job_key.strip().lower().rstrip("/").encode()).hexdigest()
    existing = db.scalar(select(ApplicationDispatchKey).where(
        ApplicationDispatchKey.user_id == user_id,
        ApplicationDispatchKey.application_id == application_id,
    ).with_for_update())
    if existing:
        if existing.idempotency_key != idempotency_key or existing.payload_hash != digest:
            raise DispatchConflict("This application already has a dispatch reservation")
        return existing
    duplicate_job = db.scalar(select(ApplicationDispatchKey).where(
        ApplicationDispatchKey.user_id == user_id,
        ApplicationDispatchKey.job_key == job_key,
    ).with_for_update())
    if duplicate_job:
        raise DispatchConflict("This job already has a dispatch reservation for this account")
    row = ApplicationDispatchKey(
        user_id=user_id, application_id=application_id, job_key=job_key,
        idempotency_key=idempotency_key, payload_hash=digest,
        status="reserved", created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise DispatchConflict("A concurrent dispatch reservation already exists") from exc
    return row


def complete_application_dispatch(db: Session, row: ApplicationDispatchKey) -> None:
    row.status = "candidate_confirmed"
    row.completed_at = datetime.now(timezone.utc)
    db.flush()
