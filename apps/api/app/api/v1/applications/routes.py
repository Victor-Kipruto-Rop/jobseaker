from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from apps.api.app.dependencies import get_current_user, get_db
from packages.database.models.identity import User
from packages.database.models.career import (
    Application, ApplicationEvent, CandidateOpportunity, RecommendationInteraction, ATSApplicationDraft, ATSActionApproval, AuditLog,
)
from packages.integrations.url_validation import validate_http_url
from packages.events.outbox import enqueue_event
from packages.applications.email_intent import classify_email
from packages.automation.ats_mapping import build_mapping
from packages.automation.browser_adapter import action_digest
from packages.security.credential_vault import encrypt_credential, decrypt_credential
import hashlib
import json
from packages.applications.fsm import STATUSES, TRANSITIONS, can_transition
from packages.automation.idempotency import (
    DispatchConflict, reserve_application_dispatch, complete_application_dispatch,
)

router = APIRouter()
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


class ApplicationApproval(BaseModel):
    confirm: bool = True
    note: str = Field(default="", max_length=1000)


class SubmissionConfirmation(BaseModel):
    confirm: bool = True
    confirmation_note: str = Field(default="", max_length=2000)
    external_receipt_url: str = Field(default="", max_length=2000)

    @field_validator("external_receipt_url")
    @classmethod
    def safe_receipt_url(cls, value):
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


class EmailIntentPreview(BaseModel):
    subject: str = Field(default="", max_length=1000)
    body: str = Field(min_length=1, max_length=30000)
    application_id: int | None = None

@router.post("/email-intent-preview")
def preview_email_intent(body: EmailIntentPreview,
                         user: User = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    """Classify candidate-supplied email text; never advances application state."""
    if body.application_id is not None:
        owned = db.scalar(select(Application).where(
            Application.id == body.application_id, Application.user_id == user.id))
        if not owned:
            raise HTTPException(status_code=404, detail="Application not found")
    result = classify_email(body.subject, body.body)
    result["application_id"] = body.application_id
    result["candidate_action_required"] = True
    return result


class ATSDraftRequest(BaseModel):
    fields: list[dict] = Field(min_length=1, max_length=250)
    candidate_values: dict[str, str] = Field(default_factory=dict)

class ATSDraftApproval(BaseModel):
    confirm: bool = False

@router.post("/{application_id}/ats-draft")
def create_ats_draft(application_id: int, body: ATSDraftRequest,
                     user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    """Persist proposed ATS field mappings for candidate review; never submits forms."""
    application = db.scalar(select(Application).where(
        Application.id == application_id, Application.user_id == user.id).with_for_update())
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    if application.status not in {"draft", "ready", "approved"}:
        raise HTTPException(status_code=409, detail="ATS mapping is locked after submission")
    mappings = build_mapping(body.fields, body.candidate_values)
    rows = [row.__dict__.copy() for row in mappings]
    stored_rows = []
    for item in rows:
        stored = item.copy()
        if stored.get("value"):
            stored["value_ciphertext"] = encrypt_credential(
                stored["value"], purpose="ats-field-value")
            stored["value"] = None
        stored_rows.append(stored)
    digest = hashlib.sha256(json.dumps(
        [application.id, stored_rows], sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    draft = db.scalar(select(ATSApplicationDraft).where(
        ATSApplicationDraft.application_id == application.id,
        ATSApplicationDraft.user_id == user.id).with_for_update())
    if draft is None:
        draft = ATSApplicationDraft(user_id=user.id, application_id=application.id)
        db.add(draft)
    draft.mappings = stored_rows
    draft.mapping_sha256 = digest
    draft.status = "needs_review" if any(x.status != "proposed" for x in mappings) else "ready_for_review"
    draft.candidate_confirmed = False
    draft.approved_at = None
    db.add(AuditLog(user_id=user.id, action="ats.mapping_proposed",
                    resource_type="application", resource_id=str(application.id),
                    metadata_json={"mapping_sha256": digest, "field_count": len(rows)}))
    db.commit()
    db.refresh(draft)
    return {"id": draft.id, "application_id": application.id, "status": draft.status,
            "mapping_sha256": digest, "mappings": rows,
            "execution_policy": "candidate_review_required"}

@router.get("/{application_id}/ats-draft")
def get_ats_draft(application_id: int, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    draft = db.scalar(select(ATSApplicationDraft).where(
        ATSApplicationDraft.application_id == application_id,
        ATSApplicationDraft.user_id == user.id))
    if not draft:
        raise HTTPException(status_code=404, detail="ATS draft not found")
    mappings = []
    for stored in draft.mappings or []:
        item = dict(stored)
        ciphertext = item.pop("value_ciphertext", None)
        if ciphertext:
            item["value"] = decrypt_credential(ciphertext, purpose="ats-field-value")
        mappings.append(item)
    return {"id": draft.id, "application_id": draft.application_id, "status": draft.status,
            "mapping_sha256": draft.mapping_sha256, "mappings": mappings,
            "candidate_confirmed": draft.candidate_confirmed,
            "approved_at": draft.approved_at,
            "execution_policy": "candidate_review_required"}

@router.post("/{application_id}/ats-draft/approve")
def approve_ats_draft(application_id: int, body: ATSDraftApproval,
                      user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    draft = db.scalar(select(ATSApplicationDraft).where(
        ATSApplicationDraft.application_id == application_id,
        ATSApplicationDraft.user_id == user.id).with_for_update())
    if not draft:
        raise HTTPException(status_code=404, detail="ATS draft not found")
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Candidate confirmation is required")
    application = db.scalar(select(Application).where(
        Application.id == application_id, Application.user_id == user.id))
    if not application or application.status not in {"draft", "ready", "approved"}:
        raise HTTPException(status_code=409, detail="Application is no longer eligible for ATS review")
    rows = draft.mappings or []
    digest = hashlib.sha256(json.dumps(
        [application_id, rows], sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    if digest != draft.mapping_sha256:
        raise HTTPException(status_code=409, detail="ATS mapping changed; regenerate and review it")
    if not rows or any(row.get("status") != "proposed" for row in rows):
        raise HTTPException(status_code=409, detail="Resolve every unknown or missing field before approval")
    from datetime import datetime, timezone
    draft.status = "approved"
    draft.candidate_confirmed = True
    draft.approved_at = datetime.now(timezone.utc)
    db.add(AuditLog(user_id=user.id, action="ats.mapping_approved",
                    resource_type="application", resource_id=str(application_id),
                    metadata_json={"mapping_sha256": digest, "candidate_confirmed": True}))
    db.commit()
    return {"status": "approved", "application_id": application_id,
            "mapping_sha256": digest, "candidate_confirmed": True,
            "external_submission_performed": False,
            "next_step": "Review and manually enter the approved values in the external ATS"}


class ATSActionApprovalRequest(BaseModel):
    confirm: bool = False

@router.post("/{application_id}/ats-draft/actions/{field_id}/approve")
def approve_ats_field_action(application_id: int, field_id: str,
                             body: ATSActionApprovalRequest,
                             user: User = Depends(get_current_user),
                             db: Session = Depends(get_db)):
    """Approve exactly one immutable ATS field fill, not the whole external submission."""
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Explicit per-action confirmation is required")
    draft = db.scalar(select(ATSApplicationDraft).where(
        ATSApplicationDraft.application_id == application_id,
        ATSApplicationDraft.user_id == user.id).with_for_update())
    if not draft or draft.status != "approved" or not draft.candidate_confirmed:
        raise HTTPException(status_code=409, detail="Approve the complete ATS mapping before approving field actions")
    mapping = next((dict(item) for item in (draft.mappings or [])
                    if str(item.get("field_id")) == field_id), None)
    if not mapping or mapping.get("status") != "proposed":
        raise HTTPException(status_code=404, detail="Approved field mapping not found")
    ciphertext = mapping.get("value_ciphertext")
    if not ciphertext:
        raise HTTPException(status_code=409, detail="Field value is not available for secure execution")
    value = decrypt_credential(ciphertext, purpose="ats-field-value")
    digest = action_digest(application_id, draft.mapping_sha256, field_id,
                           str(mapping.get("label") or ""), value)
    existing = db.scalar(select(ATSActionApproval).where(
        ATSActionApproval.user_id == user.id,
        ATSActionApproval.application_id == application_id,
        ATSActionApproval.field_id == field_id).with_for_update())
    if existing:
        if existing.action_digest != digest:
            raise HTTPException(status_code=409, detail="Field value changed; regenerate and review the ATS draft")
        return {"status": existing.status, "field_id": field_id,
                "action_digest": digest, "idempotent": True}
    approval = ATSActionApproval(
        user_id=user.id, application_id=application_id, draft_id=draft.id,
        field_id=field_id, action_digest=digest, status="approved",
    )
    db.add(approval)
    db.add(AuditLog(user_id=user.id, action="ats.field_action_approved",
                    resource_type="application", resource_id=str(application_id),
                    metadata_json={"field_id": field_id, "action_digest": digest}))
    db.commit()
    return {"status": "approved", "field_id": field_id, "action_digest": digest,
            "external_action_executed": False,
            "execution_policy": "one_approved_fill_action_only"}

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
async def create_application(body: ApplicationCreate, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db),
                       background_tasks: BackgroundTasks = BackgroundTasks()):
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
    enqueue_event(db, "application.status_changed", {
        "user_id": user.id, "application_id": row.id, "from": None, "to": "draft",
    }, partition_key=str(user.id))
    db.commit()
    db.refresh(row)
    return _serialize(row, owned if body.opportunity_id is not None else None)

@router.post("/{application_id}/approve")
def approve_application(
    application_id: int,
    body: ApplicationApproval,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record explicit candidate approval after the application draft is ready."""
    row = db.scalar(select(Application).where(
        Application.id == application_id, Application.user_id == user.id,
    ).with_for_update())
    if not row:
        raise HTTPException(status_code=404, detail="Application not found")
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Candidate approval is required")
    if row.status == "approved":
        return {"status": "already_approved", "application_id": row.id}
    if not can_transition(row.status, "approved"):
        raise HTTPException(status_code=409, detail="Only a ready application can be approved")
    row.status = "approved"
    db.add(ApplicationEvent(
        user_id=user.id, application_id=row.id, event_type="application.approved",
        details={"candidate_confirmed": True, "note": body.note},
    ))
    enqueue_event(db, "application.status_changed", {
        "user_id": user.id, "application_id": row.id,
        "from": "ready", "to": "approved", "candidate_confirmed": True,
    }, partition_key=str(user.id))
    db.commit()
    return {"status": "approved", "application_id": row.id}


@router.post("/{application_id}/confirm-submission")
def confirm_submission(
    application_id: int,
    body: SubmissionConfirmation,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    """Record that the candidate submitted on the external ATS themselves."""
    row = db.scalar(select(Application).where(
        Application.id == application_id, Application.user_id == user.id,
    ).with_for_update())
    if not row:
        raise HTTPException(status_code=404, detail="Application not found")
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Candidate submission confirmation is required")
    if row.status == "submitted":
        return {"status": "already_confirmed", "application_id": row.id,
                "application_status": row.status}
    if row.status != "approved":
        raise HTTPException(status_code=409, detail="Approve the application before confirming submission")
    job_key = (
        f"opportunity:{row.opportunity_id}" if row.opportunity_id
        else (row.job_url or f"application:{row.id}")
    )
    try:
        reservation = reserve_application_dispatch(
            db, user_id=user.id, application_id=row.id,
            idempotency_key=idempotency_key or f"candidate-confirmed:{row.id}",
            payload={
                "job_key": job_key, "candidate_confirmed": True,
                "external_receipt_url": body.external_receipt_url,
            },
        )
    except DispatchConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    row.status = "submitted"
    row.applied_at = datetime.now(timezone.utc)
    complete_application_dispatch(db, reservation)
    db.add(ApplicationEvent(
        user_id=user.id, application_id=row.id,
        event_type="application.submission_confirmed",
        details={
            "candidate_confirmed": True,
            "confirmation_note": body.confirmation_note,
            "external_receipt_url": body.external_receipt_url,
            "external_ats_acceptance_verified": False,
        },
    ))
    enqueue_event(db, "application.status_changed", {
        "user_id": user.id, "application_id": row.id,
        "from": "approved", "to": "submitted",
        "submission_recorded": True, "external_ats_acceptance_verified": False,
    }, partition_key=str(user.id))
    db.commit()
    return {"status": "submission_recorded", "application_id": row.id,
            "external_ats_acceptance_verified": False}


@router.patch("/{application_id}")
async def update_application(application_id: int, body: ApplicationUpdate,
                       user: User = Depends(get_current_user), db: Session = Depends(get_db),
                       background_tasks: BackgroundTasks = BackgroundTasks(),
                       idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    row = db.scalar(select(Application).where(
        Application.id == application_id, Application.user_id == user.id))
    if not row:
        raise HTTPException(status_code=404, detail="Application not found")
    values = body.model_dump(exclude_unset=True)
    status = values.get("status")
    if status is not None and status not in STATUSES:
        raise HTTPException(status_code=422, detail="Unsupported application status")
    if status in {"approved", "submitted"}:
        raise HTTPException(
            status_code=409,
            detail="Use the explicit candidate approval or submission confirmation action",
        )
    before = row.status
    if status is not None and status != before and status not in TRANSITIONS.get(before, set()):
        raise HTTPException(status_code=409, detail="Invalid application status transition: " + before + " -> " + status)
    dispatch_reservation = None
    if status == "submitted" and before != "submitted":
        job_key = (
            f"opportunity:{row.opportunity_id}" if row.opportunity_id
            else (row.job_url or f"application:{row.id}")
        )
        try:
            dispatch_reservation = reserve_application_dispatch(
                db, user_id=user.id, application_id=row.id,
                idempotency_key=idempotency_key or f"application:{row.id}:submitted",
                payload={"job_key": job_key, "job_url": row.job_url,
                         "role_title": row.role_title, "company_name": row.company_name},
            )
        except DispatchConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    for key, value in values.items():
        if value is not None:
            setattr(row, key, value)
    if status == "submitted" and row.applied_at is None:
        row.applied_at = datetime.now(timezone.utc)
    if dispatch_reservation is not None:
        complete_application_dispatch(db, dispatch_reservation)
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
    if status and status != before:
        enqueue_event(
            db,
            "application.status_changed",
            {"user_id": user.id, "application_id": row.id, "from": before, "to": status,
             "submission_recorded": status == "submitted"},
            partition_key=str(user.id),
        )
    db.commit()
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
