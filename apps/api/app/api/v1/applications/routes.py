from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from apps.api.app.dependencies import get_current_user, get_db
from packages.database.models.identity import User
from packages.database.models.career import Application, ApplicationEvent

router = APIRouter()
STATUSES = {"draft", "ready", "approved", "submitted", "screening", "interview",
            "assessment", "offer", "rejected", "withdrawn", "archived"}

class ApplicationCreate(BaseModel):
    role_title: str = Field(min_length=2, max_length=250)
    company_name: str = Field(default="", max_length=250)
    job_url: str = Field(default="", max_length=2000)
    notes: str = Field(default="", max_length=10000)
    opportunity_id: int | None = None

class ApplicationUpdate(BaseModel):
    status: str | None = None
    notes: str | None = Field(default=None, max_length=10000)
    job_url: str | None = Field(default=None, max_length=2000)

def _serialize(row):
    return {"id": row.id, "role_title": row.role_title, "company_name": row.company_name,
            "status": row.status, "job_url": row.job_url, "notes": row.notes,
            "applied_at": row.applied_at, "created_at": row.created_at}

@router.get("")
def list_applications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Application).where(Application.user_id == user.id)
                      .order_by(Application.created_at.desc()).limit(500)).all()
    return [_serialize(row) for row in rows]

@router.post("", status_code=201)
def create_application(body: ApplicationCreate, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    row = Application(user_id=user.id, **body.model_dump())
    db.add(row)
    db.flush()
    db.add(ApplicationEvent(user_id=user.id, application_id=row.id,
                            event_type="application.created", details={"status": "draft"}))
    db.commit()
    db.refresh(row)
    return _serialize(row)

@router.patch("/{application_id}")
def update_application(application_id: int, body: ApplicationUpdate,
                       user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(Application).where(
        Application.id == application_id, Application.user_id == user.id))
    if not row:
        raise HTTPException(status_code=404, detail="Application not found")
    values = body.model_dump(exclude_unset=True)
    status = values.get("status")
    if status is not None and status not in STATUSES:
        raise HTTPException(status_code=422, detail="Unsupported application status")
    before = row.status
    for key, value in values.items():
        if value is not None:
            setattr(row, key, value)
    if status == "submitted" and row.applied_at is None:
        row.applied_at = datetime.now(timezone.utc)
    if status and status != before:
        db.add(ApplicationEvent(user_id=user.id, application_id=row.id,
                                event_type="application.status_changed",
                                details={"from": before, "to": status}))
    db.commit()
    return _serialize(row)

@router.get("/{application_id}/events")
def application_events(application_id: int, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    row = db.scalar(select(Application).where(
        Application.id == application_id, Application.user_id == user.id))
    if not row:
        raise HTTPException(status_code=404, detail="Application not found")
    events = db.scalars(select(ApplicationEvent).where(
        ApplicationEvent.application_id == application_id, ApplicationEvent.user_id == user.id
    ).order_by(ApplicationEvent.created_at.asc())).all()
    return [{"id": e.id, "event_type": e.event_type, "details": e.details,
             "created_at": e.created_at} for e in events]
