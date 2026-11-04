"""Durable RQ dispatcher and worker for assistant document indexing."""
import base64
from datetime import datetime, timedelta, timezone
from sqlalchemy import or_, select
from redis import Redis
from rq import Queue, Retry
from packages.database.sessions import SessionLocal
from packages.database.models.assistant_jobs import AssistantIngestionJob
from packages.database.models.assistant import AssistantEntity, AssistantFact, AssistantRelation, AssistantMemory
from packages.database.models.assistant import AssistantPreference
from packages.assistant.engine import sanitize, remember
from packages.assistant.ingestion import parse_document
from packages.security.credential_vault import encrypt_credential, decrypt_credential

def encrypt_ingestion_payload(user_id: int, job_id: str, payload: bytes) -> str:
    value = base64.b64encode(payload).decode("ascii")
    return encrypt_credential(value, purpose=f"assistant-ingestion:{user_id}:{job_id}")

def dispatch_pending_ingestion_jobs(redis_url: str, batch_size: int = 20) -> int:
    """Publish durable DB outbox rows; stale leases are safely redelivered."""
    now = datetime.now(timezone.utc)
    queued_cutoff = now - timedelta(minutes=15)
    processing_cutoff = now - timedelta(minutes=20)
    failed_cutoff = now - timedelta(minutes=6)
    db = SessionLocal()
    dispatches = []
    try:
        rows = db.scalars(select(AssistantIngestionJob).where(or_(
            (AssistantIngestionJob.status == "queued") &
            ((AssistantIngestionJob.dispatched_at.is_(None)) |
             (AssistantIngestionJob.dispatched_at < queued_cutoff)),
            (AssistantIngestionJob.status == "processing") &
            (AssistantIngestionJob.updated_at < processing_cutoff),
            (AssistantIngestionJob.status == "failed") &
            (AssistantIngestionJob.attempts < 3) &
            (AssistantIngestionJob.updated_at < failed_cutoff)
        )).order_by(AssistantIngestionJob.created_at.asc()).limit(batch_size).with_for_update(skip_locked=True)).all()
        for row in rows:
            if row.status in {"processing", "failed"}:
                row.status = "queued"
            row.dispatch_attempts = int(row.dispatch_attempts or 0) + 1
            row.dispatched_at = now
            dispatches.append((row.job_id, row.dispatch_attempts))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    if not dispatches:
        return 0
    try:
        queue = Queue("assistant", connection=Redis.from_url(redis_url))
    except Exception:
        db = SessionLocal()
        try:
            for job_id, attempt in dispatches:
                row = db.scalar(select(AssistantIngestionJob).where(
                    AssistantIngestionJob.job_id == job_id).with_for_update())
                if row and row.status == "queued" and row.dispatch_attempts == attempt:
                    row.dispatched_at = None
            db.commit()
        finally:
            db.close()
        raise
    published = 0
    for job_id, attempt in dispatches:
        try:
            queue.enqueue("packages.assistant.jobs.process_ingestion_job", job_id,
                job_id=f"assistant-ingest-{job_id}-{attempt}", job_timeout=900,
                result_ttl=86400, failure_ttl=604800,
                retry=Retry(max=2, interval=[60, 300]))
            published += 1
        except Exception:
            db = SessionLocal()
            try:
                row = db.scalar(select(AssistantIngestionJob).where(
                    AssistantIngestionJob.job_id == job_id).with_for_update())
                if row and row.status == "queued" and row.dispatch_attempts == attempt:
                    row.dispatched_at = None
                    db.commit()
            finally:
                db.close()
    return published

def purge_expired_assistant_memory(batch_size: int = 1000) -> int:
    """Delete expired episodic records and their derived facts/graph nodes."""
    now = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        rows = db.scalars(select(AssistantMemory).where(
            AssistantMemory.expires_at.is_not(None), AssistantMemory.expires_at <= now
        ).order_by(AssistantMemory.expires_at.asc()).limit(batch_size).with_for_update(skip_locked=True)).all()
        memory_ids = [row.id for row in rows]
        if not memory_ids:
            return 0
        db.query(AssistantFact).filter(AssistantFact.source_memory_id.in_(memory_ids)).delete(synchronize_session=False)
        entities = db.scalars(select(AssistantEntity).where(AssistantEntity.source_memory_id.in_(memory_ids))).all()
        entity_ids = [entity.id for entity in entities]
        if entity_ids:
            db.query(AssistantRelation).filter(or_(
                AssistantRelation.source_entity_id.in_(entity_ids),
                AssistantRelation.target_entity_id.in_(entity_ids)
            )).delete(synchronize_session=False)
            db.query(AssistantEntity).filter(AssistantEntity.id.in_(entity_ids)).delete(synchronize_session=False)
        db.query(AssistantMemory).filter(AssistantMemory.id.in_(memory_ids)).delete(synchronize_session=False)
        db.commit()
        return len(memory_ids)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
def process_ingestion_job(job_id: str) -> dict:
    db = SessionLocal()
    try:
        job = db.scalar(select(AssistantIngestionJob).where(
            AssistantIngestionJob.job_id == job_id).with_for_update())
        if job is None:
            return {"status": "missing"}
        now = datetime.now(timezone.utc)
        if job.status in {"completed", "cancelled"}:
            return {"status": job.status}
        updated_at = job.updated_at
        if updated_at and updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        if job.status == "processing" and updated_at and updated_at > now - timedelta(minutes=20):
            return {"status": "already_processing"}
        if not job.payload_ciphertext:
            job.status = "cancelled"
            db.commit()
            return {"status": "cancelled"}
        job.status = "processing"
        job.attempts += 1
        job.updated_at = now
        db.commit()

        encoded = decrypt_credential(job.payload_ciphertext,
            purpose=f"assistant-ingestion:{job.user_id}:{job.job_id}")
        raw = base64.b64decode(encoded)
        extracted = parse_document(job.filename, job.content_type, raw)
        clean = sanitize(extracted)
        if len(clean.strip()) < 20:
            raise ValueError("No usable text could be extracted.")

        # Lock consent first, then the job row. Deletion uses the same lock order.
        preference = db.scalar(select(AssistantPreference).where(
            AssistantPreference.user_id == job.user_id).with_for_update())
        job = db.scalar(select(AssistantIngestionJob).where(
            AssistantIngestionJob.job_id == job_id).with_for_update())
        if not preference or not preference.memory_enabled or not job or job.status == "cancelled":
            if job:
                job.status = "cancelled"
                job.payload_ciphertext = ""
                db.commit()
            return {"status": "cancelled"}
        if job.status == "completed":
            return {"status": "completed"}
        job.memory_id = remember(db, job.user_id, clean, source="document")
        job.characters_indexed = len(clean)
        job.status = "completed"
        job.payload_ciphertext = ""
        job.completed_at = datetime.now(timezone.utc)
        job.updated_at = job.completed_at
        job.last_error = None
        db.commit()
        return {"status": job.status, "memory_id": job.memory_id}
    except Exception as exc:
        db.rollback()
        job = db.scalar(select(AssistantIngestionJob).where(
            AssistantIngestionJob.job_id == job_id).with_for_update())
        if job:
            if job.status == "cancelled":
                job.payload_ciphertext = ""
            else:
                job.status = "failed"
                job.last_error = type(exc).__name__
                job.updated_at = datetime.now(timezone.utc)
                if job.attempts >= 3:
                    job.payload_ciphertext = ""
            db.commit()
        raise
    finally:
        db.close()
