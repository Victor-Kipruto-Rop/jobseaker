"""RQ worker entry point for assistant document indexing."""
import base64
from datetime import datetime, timezone
from sqlalchemy import select
from packages.database.sessions import SessionLocal
from packages.database.models.assistant_jobs import AssistantIngestionJob
from packages.database.models.assistant import AssistantPreference
from packages.assistant.engine import sanitize, remember
from packages.assistant.ingestion import parse_document
from packages.security.credential_vault import encrypt_credential, decrypt_credential

def encrypt_ingestion_payload(user_id: int, job_id: str, payload: bytes) -> str:
    value = base64.b64encode(payload).decode("ascii")
    return encrypt_credential(value, purpose=f"assistant-ingestion:{user_id}:{job_id}")

def process_ingestion_job(job_id: str) -> dict:
    db = SessionLocal()
    try:
        job = db.scalar(select(AssistantIngestionJob).where(AssistantIngestionJob.job_id == job_id))
        if job is None:
            return {"status": "missing"}
        preference = db.scalar(select(AssistantPreference).where(AssistantPreference.user_id == job.user_id))
        if not preference or not preference.memory_enabled or job.status == "cancelled":
            job.status = "cancelled"
            job.payload_ciphertext = ""
            db.commit()
            return {"status": "cancelled"}
        job.status = "processing"
        job.attempts += 1
        db.commit()
        encoded = decrypt_credential(job.payload_ciphertext,
            purpose=f"assistant-ingestion:{job.user_id}:{job.job_id}")
        raw = base64.b64decode(encoded)
        extracted = parse_document(job.filename, job.content_type, raw)
        clean = sanitize(extracted)
        if len(clean.strip()) < 20:
            raise ValueError("No usable text could be extracted.")
        job.memory_id = remember(db, job.user_id, clean, source="document")
        job.characters_indexed = len(clean)
        job.status = "completed"
        job.payload_ciphertext = ""
        job.completed_at = datetime.now(timezone.utc)
        job.last_error = None
        db.commit()
        return {"status": job.status, "memory_id": job.memory_id}
    except Exception as exc:
        db.rollback()
        job = db.scalar(select(AssistantIngestionJob).where(AssistantIngestionJob.job_id == job_id))
        if job:
            job.status = "failed"
            job.last_error = type(exc).__name__
            if job.attempts >= 3:
                job.payload_ciphertext = ""
            db.commit()
        raise
    finally:
        db.close()
