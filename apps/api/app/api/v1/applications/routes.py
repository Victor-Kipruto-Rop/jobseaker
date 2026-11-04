from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from apps.api.app.dependencies import get_current_user, get_db
from packages.database.models.identity import User
from packages.database.models.career import (
    Application, ApplicationEvent, CandidateOpportunity, RecommendationInteraction,
)
from packages.integrations.url_validation import validate_http_url
from packages.events.kafka import publish_event

router = APIRouter()
STATUSES = {"draft", "ready", "approved", "submitted", "screening", "interview",
            "assessment", "offer", "accepted", "rejected", "withdrawn", "archived"}
TRANSITIONS = {
    "draft": {"ready", "withdrawn", "archived"},
    # Approval is granted only through the user-owned approval workflow service.
    "ready": {"draft", "withdrawn", "archived"},
    "approved": {"ready", "submitted", "withdrawn"},
    "submitted": {"screening", "interview", "assessment", "rejected", "withdrawn"},
    "screening": {"interview", "assessment", "rejected", "withdrawn"},
    "interview": {"assessment", "offer", "rejected", "withdrawn"},
    "assessment": {"interview", "offer", "rejected", "withdrawn"},
    "offer": {"accepted", "rejected", "withdrawn"},
    "accepted": {"archived"}, "rejected": {"archived"},
    "withdrawn": {"archived"}, "archived": set(),
}

class ApplicationCreate(BaseModel):
    role_title: str = Field(min_length=2, max_length=250)
    company_name: str = Field(default="", max_length=250)
    job_url: str = Field(default="", max_length=2000)
    notes: str = Field(default="", max_length=10000)
    opportunity_id: int | None = None

    @field_validator("job_url")
    @classmethod
    def safe_job_url(cls, value):
        return validate_http_url(value or "")

class ApplicationUpdate(BaseModel):
    status: str | None = None
    notes: str | None = Field(default=None, max_length=10000)
    job_url: str | None = Field(default=None, max_length=2000)

    @field_validator("job_url")
    @classmethod
    def safe_job_url(cls, value):
        return validate_http_url(value or "")

def _serialize(row, opportunity=None):
    snapshot = row.company_profile_snapshot or {}
    return {"id": row.id, "role_title": row.role_title, "company_name": row.company_name,
            "company_id": opportunity.company_id if opportunity else snapshot.get("company_id"),
            "company_logo_url": snapshot.get("logo_url") or (opportunity.company_logo_url if opportunity else ""),
            "company_favicon_url": snapshot.get("favicon_url") or (opportunity.company_favicon_url if opportunity else ""),
            "company_website": snapshot.get("website") or (opportunity.company_website if opportunity else ""),
            "company_domain": snapshot.get("domain") or (opportunity.company_domain if opportunity else ""),
            "company_description": snapshot.get("description") or (opportunity.company_description if opportunity else ""),
            "company_brand_color": snapshot.get("brand_color") or (opportunity.company_brand_color if opportunity else ""),
            "job_description_snapshot": row.job_description_snapshot,
            "company_profile_snapshot": snapshot,
            "status": row.status, "job_url": row.job_url, "notes": row.notes,
            "applied_at": row.applied_at, "created_at": row.created_at}

@router.get("")
def list_applications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Application).where(Application.user_id == user.id)
                      .order_by(Application.created_at.desc()).limit(500)).all()
    opportunity_ids = {row.opportunity_id for row in rows if row.opportunity_id is not None}
    opportunities = {}
    if opportunity_ids:
        opportunities = {
            item.id: item for item in db.scalars(select(CandidateOpportunity).where(
                CandidateOpportunity.id.in_(opportunity_ids),
                CandidateOpportunity.user_id == user.id,
            )).all()
        }
    return [_serialize(row, opportunities.get(row.opportunity_id)) for row in rows]

@router.post("", status_code=201)
async def create_application(body: ApplicationCreate, background_tasks: BackgroundTasks, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    if body.opportunity_id is not None:
        owned = db.scalar(select(CandidateOpportunity).where(
            CandidateOpportunity.id == body.opportunity_id, CandidateOpportunity.user_id == user.id))
        if not owned:
            raise HTTPException(status_code=404, detail="Opportunity not found")
    opportunity = owned if body.opportunity_id is not None else None
    company_snapshot = ({
        "name": opportunity.company,
        "website": opportunity.company_website,
        "domain": opportunity.company_domain,
        "logo_url": opportunity.company_logo_url,
        "favicon_url": opportunity.company_favicon_url,
        "description": opportunity.company_description,
        "brand_color": opportunity.company_brand_color,
        "company_id": opportunity.company_id,
    } if opportunity else {})
    row = Application(
        user_id=user.id,
        job_description_snapshot=opportunity.description if opportunity else "",
        company_profile_snapshot=company_snapshot,
        **body.model_dump(),
    )
    db.add(row)
    db.flush()
    db.add(ApplicationEvent(user_id=user.id, application_id=row.id,
                            event_type="application.created", details={"status": "draft"}))
    db.commit()
    db.refresh(row)
    background_tasks.add_task(publish_event, "application.status_changed", {
        "user_id": user.id, "application_id": row.id, "from": None, "to": "draft",
    }, key=str(row.id))
    return _serialize(row, owned if body.opportunity_id is not None else None)

@router.patch("/{application_id}")
async def update_application(application_id: int, body: ApplicationUpdate,
                       background_tasks: BackgroundTasks,
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
    if status is not None and status != before and status not in TRANSITIONS.get(before, set()):
        raise HTTPException(status_code=409, detail="Invalid application status transition: " + before + " -> " + status)
    for key, value in values.items():
        if value is not None:
            setattr(row, key, value)
    if status == "submitted" and row.applied_at is None:
        row.applied_at = datetime.now(timezone.utc)
    if status == "submitted" and before != "submitted" and row.job_url:
        db.add(RecommendationInteraction(
            user_id=user.id, opportunity_id=row.opportunity_id,
            item_key=row.job_url, event_type="apply",
            recommendation_source="",
            feature_snapshot={},
        ))
    if status and status != before:
        db.add(ApplicationEvent(user_id=user.id, application_id=row.id,
                                event_type="application.status_changed",
                                details={"from": before, "to": status}))
    changed_fields = {key: True for key in values if key != "status" and values[key] is not None}
    if changed_fields:
        db.add(ApplicationEvent(user_id=user.id, application_id=row.id,
                                event_type="application.details_updated",
                                details={"fields": changed_fields}))
    db.commit()
    if status and status != before:
        background_tasks.add_task(
            publish_event,
            "application.dispatched" if status == "submitted" else "application.status_changed",
            {"user_id": user.id, "application_id": row.id, "from": before, "to": status},
            key=str(row.id),
        )
    opportunity = None
    if row.opportunity_id is not None:
        opportunity = db.scalar(select(CandidateOpportunity).where(
            CandidateOpportunity.id == row.opportunity_id,
            CandidateOpportunity.user_id == user.id,
        ))
    return _serialize(row, opportunity)

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
