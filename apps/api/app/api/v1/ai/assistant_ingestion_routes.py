"""Authenticated asynchronous document ingestion and job status API."""
from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from redis import Redis
from rq import Queue
from sqlalchemy import select
from sqlalchemy.orm import Session
from apps.api.app.core.config import get_settings
from apps.api.app.dependencies import get_current_user, get_db
from packages.database.models.identity import User
from packages.database.models.assistant import AssistantPreference
from packages.database.models.assistant_jobs import AssistantIngestionJob
from packages.assistant.ingestion import MAX_BYTES
from packages.assistant.jobs import encrypt_ingestion_payload

router = APIRouter()

@router.post("/assistant/ingest-async", status_code=202)
async def enqueue_ingestion(file: UploadFile = File(...), user: User = Depends(get_current_user),
                            db: Session = Depends(get_db)):
    pref = db.scalar(select(AssistantPreference).where(AssistantPreference.user_id == user.id))
    if not pref or not pref.memory_enabled:
        raise HTTPException(status_code=409, detail="Enable assistant memory before adding personal documents.")
    payload = await file.read(MAX_BYTES + 1)
    await file.close()
    if not payload:
        raise HTTPException(status_code=422, detail="The uploaded file is empty.")
    if len(payload) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="The uploaded file exceeds the 12 MB limit.")
    job_id = str(uuid.uuid4())
    filename = (file.filename or "upload")[:255]
    content_type = (file.content_type or "application/octet-stream")[:160]
    try:
        ciphertext = encrypt_ingestion_payload(user.id, job_id, payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Configure the assistant encryption keyring before ingesting documents.") from exc
    job = AssistantIngestionJob(job_id=job_id, user_id=user.id, filename=filename,
        content_type=content_type, payload_ciphertext=ciphertext, status="queued")
    db.add(job)
    db.commit()
    try:
        queue = Queue("assistant", connection=Redis.from_url(get_settings().redis_url))
        queue.enqueue("packages.assistant.jobs.process_ingestion_job", job_id,
            job_id=f"assistant-ingest-{job_id}", job_timeout=900, result_ttl=86400, failure_ttl=604800)
    except Exception as exc:
        db.delete(job)
        db.commit()
        raise HTTPException(status_code=503, detail="Assistant ingestion queue is unavailable. Retry shortly.") from exc
    return {"job_id": job_id, "status": "queued", "filename": filename}

@router.get("/assistant/ingestion/{job_id}")
def ingestion_status(job_id: str, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    job = db.scalar(select(AssistantIngestionJob).where(
        AssistantIngestionJob.job_id == job_id, AssistantIngestionJob.user_id == user.id))
    if not job:
        raise HTTPException(status_code=404, detail="Ingestion job not found.")
    return {"job_id": job.job_id, "status": job.status, "filename": job.filename,
        "attempts": job.attempts, "characters_indexed": job.characters_indexed,
        "error": job.last_error, "created_at": job.created_at, "completed_at": job.completed_at}

@router.delete("/assistant/ingestion/{job_id}")
def cancel_ingestion(job_id: str, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    job = db.scalar(select(AssistantIngestionJob).where(
        AssistantIngestionJob.job_id == job_id, AssistantIngestionJob.user_id == user.id))
    if not job:
        raise HTTPException(status_code=404, detail="Ingestion job not found.")
    if job.status in {"queued", "failed"}:
        job.status = "cancelled"
        job.payload_ciphertext = ""
        db.commit()
    return {"cancelled": job.status == "cancelled"}
