from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from apps.api.app.core.config import get_settings
from apps.api.app.core.redis_limits import enforce_rate_limit
from apps.api.app.dependencies import get_current_user, get_verified_user, get_db
from packages.database.models.identity import User
from packages.database.models.career import EmailAccount, EmailMessage
from packages.integrations.gmail.client import create_authorization, complete_authorization, sync_messages

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
    return RedirectResponse(get_settings().web_app_url + "/inbox?gmail=connected")

@router.get("/account")
def account(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(EmailAccount).where(
        EmailAccount.user_id == user.id, EmailAccount.provider == "gmail"))
    if not row:
        return {"connected": False, "read_only": True}
    return {"connected": True, "email": row.email, "last_synced_at": row.last_synced_at,
            "scopes": row.scopes, "read_only": True}

@router.post("/sync")
def sync(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    enforce_rate_limit(f"gmail-sync:{user.id}", limit=10, window_seconds=3600)
    try:
        return sync_messages(db, user.id, limit=200)
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
             "action_required": row.action_required, "received_at": row.received_at}
            for row in rows]

@router.delete("/account")
def disconnect(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account_row = db.scalar(select(EmailAccount).where(
        EmailAccount.user_id == user.id, EmailAccount.provider == "gmail"))
    if account_row:
        db.execute(delete(EmailMessage).where(EmailMessage.account_id == account_row.id))
        db.delete(account_row)
        db.commit()
    return {"connected": False}
