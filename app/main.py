from fastapi import FastAPI, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db, init_db
from app.models import Application, Job, OutreachContact
from app.services.outreach_import import import_outreach_csv

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", description="Local-first job intelligence and application tracker")


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.app_env, "automation_enabled": False}


@app.get(f"{settings.api_prefix}/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db)):
    return {
        "outreach_contacts": db.scalar(select(func.count()).select_from(OutreachContact)) or 0,
        "jobs": db.scalar(select(func.count()).select_from(Job)) or 0,
        "applications": db.scalar(select(func.count()).select_from(Application)) or 0,
        "gmail_monitoring_enabled": settings.gmail_enabled,
        "job_discovery_enabled": settings.job_discovery_enabled,
        "auto_submission_enabled": settings.auto_submission_enabled and not settings.global_automation_paused,
    }


@app.post(f"{settings.api_prefix}/import/outreach/preview")
async def preview_outreach(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a CSV file.")
    try:
        report = import_outreach_csv(db, await file.read(), dry_run=True)
        return report.as_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post(f"{settings.api_prefix}/import/outreach")
async def import_outreach(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a CSV file.")
    try:
        report = import_outreach_csv(db, await file.read(), dry_run=False)
        return report.as_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
