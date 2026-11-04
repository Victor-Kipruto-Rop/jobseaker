from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from apps.api.app.core.config import get_settings
from apps.api.app.core.redis_limits import enforce_rate_limit
from apps.api.app.dependencies import get_current_user, get_verified_user, get_db
from packages.database.models.identity import User
from packages.database.models.career import EmailAccount, EmailMessage, Application, ApplicationEvent
from packages.integrations.gmail.client import create_authorization, complete_authorization, sync_messages
from packages.events.outbox import enqueue_event
from packages.applications.fsm import can_transition

router = APIRouter(prefix="/gmail")
oauth_callback_router = APIRouter(prefix="/gmail")

@router.post("/authorize")
def authorize(user: User = Depends(get_verified_user), db: Session = Depends(get_db)):
    enforce_rate_limit(f"gmail-oauth:{user.id}", limit=5, window_seconds=3600)
    try:
        return {"authorization_url": create_authorization(db, user.id),
                "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
                "read_only": True}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Unable to start Gmail authorization. Check OAuth client configuration.") from exc

@oauth_callback_router.get("/callback")
def callback(state: str = Query(min_length=20), code: str = Query(min_length=5),
             db: Session = Depends(get_db)):
    try:
        complete_authorization(db, state, code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Gmail authorization could not be completed.") from exc
    return RedirectResponse(get_settings().web_app_url + "/settings?gmail=connected")

@router.get("/account")
def account(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(EmailAccount).where(
        EmailAccount.user_id == user.id, EmailAccount.provider == "gmail"))
    if not row:
        return {"connected": False, "read_only": True}
    return {"connected": True, "email": row.email, "last_synced_at": row.last_synced_at,
            "scopes": row.scopes, "read_only": True}

@router.post("/sync")
def sync(user: User = Depends(get_current_user), db: Session = Depends(get_db),
         background_tasks: BackgroundTasks = BackgroundTasks()):
    enforce_rate_limit(f"gmail-sync:{user.id}", limit=10, window_seconds=3600)
    try:
        result = sync_messages(db, user.id, limit=200)
        if result.get("new_messages", 0):
            account_row = db.scalar(select(EmailAccount).where(
                EmailAccount.user_id == user.id, EmailAccount.provider == "gmail"))
            rows = db.scalars(select(EmailMessage).where(
                EmailMessage.user_id == user.id,
                EmailMessage.account_id == account_row.id,
            ).order_by(EmailMessage.received_at.desc().nullslast()).limit(
                min(int(result["new_messages"]), 200)
            )).all() if account_row else []
            for message in rows:
                enqueue_event(
                    db, "email.classified",
                    {
                        "user_id": user.id, "email_message_id": message.id,
                        "classification": message.classification,
                        "confidence": message.confidence,
                        "action_required": message.action_required,
                    },
                    partition_key=str(user.id),
                )
            db.commit()
        return result
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail="Gmail synchronization failed. Reconnect and retry if authorization expired.") from exc

@router.get("/messages")
def messages(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account_row = db.scalar(select(EmailAccount).where(
        EmailAccount.user_id == user.id, EmailAccount.provider == "gmail"))
    if not account_row:
        return []
    rows = db.scalars(select(EmailMessage).where(
        EmailMessage.user_id == user.id, EmailMessage.account_id == account_row.id
    ).order_by(EmailMessage.received_at.desc().nullslast()).limit(300)).all()
    return [{"id": row.id, "thread_id": row.gmail_thread_id, "sender": row.sender,
             "recipient": row.recipient, "subject": row.subject, "snippet": row.snippet,
             "classification": row.classification, "confidence": row.confidence,
             "action_required": row.action_required, "application_id": row.application_id,
             "intent": row.intent, "suggested_status": row.suggested_status,
             "intent_confidence": row.intent_confidence,
             "interview_proposed_text": row.interview_proposed_text,
             "classification_evidence": row.classification_evidence,
             "state_change_requires_confirmation": True,
             "received_at": row.received_at}
            for row in rows]



class ConfirmEmailTransition(BaseModel):
    confirm: bool = True
    note: str = Field(default="", max_length=1000)


@router.post("/messages/{email_id}/confirm-status")
def confirm_email_status(
    email_id: int,
    body: ConfirmEmailTransition,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Apply a proposed lifecycle change only after explicit candidate confirmation."""
    enforce_rate_limit(f"gmail-confirm-status:{user.id}", limit=30, window_seconds=3600)
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Candidate confirmation is required")
    message = db.scalar(select(EmailMessage).where(
        EmailMessage.id == email_id, EmailMessage.user_id == user.id,
    ).with_for_update())
    if not message:
        raise HTTPException(status_code=404, detail="Email message not found")
    if not message.application_id or not message.suggested_status:
        raise HTTPException(status_code=409, detail="This email has no unambiguous application status suggestion")
    evidence = message.classification_evidence or {}
    matched = evidence.get("matched_phrases") or []
    if (message.intent_confidence is None or message.intent_confidence < 0.75
            or "ambiguous_application_match" in matched
            or not any(item in matched for item in (
                "matched_application_role", "matched_application_company",
            ))):
        raise HTTPException(status_code=409, detail="Email evidence is insufficient for a lifecycle update")
    application = db.scalar(select(Application).where(
        Application.id == message.application_id, Application.user_id == user.id,
    ).with_for_update())
    if not application:
        raise HTTPException(status_code=404, detail="Linked application not found")
    target = message.suggested_status
    if application.status == target:
        return {"status": "already_applied", "application_id": application.id,
                "application_status": application.status}
    if not can_transition(application.status, target):
        raise HTTPException(
            status_code=409,
            detail=f"Email suggestion cannot move application from {application.status} to {target}",
        )
    before = application.status
    application.status = target
    if target == "submitted" and application.applied_at is None:
        application.applied_at = message.received_at
    db.add(ApplicationEvent(
        user_id=user.id, application_id=application.id,
        event_type="application.email_transition_confirmed",
        details={
            "from": before, "to": target, "email_message_id": message.id,
            "intent": message.intent, "confidence": message.intent_confidence,
            "evidence": evidence, "candidate_note": body.note,
            "candidate_confirmed": True,
        },
    ))
    enqueue_event(db, "application.status_changed", {
        "user_id": user.id, "application_id": application.id,
        "from": before, "to": target, "source": "candidate_confirmed_email",
        "email_message_id": message.id,
    }, partition_key=str(user.id))
    db.commit()
    return {"status": "updated", "application_id": application.id,
            "from": before, "to": target, "evidence_email_id": message.id}

@router.delete("/account")
def disconnect(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account_row = db.scalar(select(EmailAccount).where(
        EmailAccount.user_id == user.id, EmailAccount.provider == "gmail"))
    if account_row:
        db.execute(delete(EmailMessage).where(EmailMessage.account_id == account_row.id))
        db.delete(account_row)
        db.commit()
    return {"connected": False}
