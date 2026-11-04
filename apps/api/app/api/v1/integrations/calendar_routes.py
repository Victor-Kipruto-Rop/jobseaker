"""Separate, candidate-authorized Google Calendar event synchronization."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.core.config import get_settings
from apps.api.app.core.redis_limits import enforce_rate_limit
from apps.api.app.dependencies import get_current_user, get_verified_user, get_db
from packages.database.models.identity import User
from packages.database.models.career import (
    CalendarAccount, CalendarOAuthState, Interview, Application, AuditLog,
)
from packages.security.credential_vault import (
    encrypt_credential, decrypt_credential, rewrap_credential, credential_needs_rotation,
)
from packages.ops.circuit_breaker import CircuitBreaker

router = APIRouter(prefix="/calendar")
oauth_callback_router = APIRouter(prefix="/calendar")
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
_CALENDAR_BREAKER = CircuitBreaker(failure_threshold=5, recovery_seconds=60.0)


def _flow(state: str | None = None) -> Flow:
    settings = get_settings()
    if not settings.calendar_enabled or not settings.gmail_client_secret_file:
        raise RuntimeError("Enable CALENDAR_ENABLED and configure the Google OAuth client secret file first.")
    flow = Flow.from_client_secrets_file(
        settings.gmail_client_secret_file, scopes=SCOPES, state=state,
    )
    flow.redirect_uri = settings.calendar_redirect_uri
    return flow


@router.post("/authorize")
def authorize(user: User = Depends(get_verified_user), db: Session = Depends(get_db)):
    enforce_rate_limit(f"calendar-oauth:{user.id}", limit=5, window_seconds=3600)
    state = secrets.token_urlsafe(32)
    try:
        flow = _flow(state)
        url, _ = flow.authorization_url(
            access_type="offline", include_granted_scopes="true", prompt="consent",
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Google Calendar OAuth is not configured") from exc
    db.add(CalendarOAuthState(
        user_id=user.id, state_hash=hashlib.sha256(state.encode()).hexdigest(),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    ))
    db.commit()
    return {"authorization_url": url, "scopes": SCOPES, "write_scope": True}


@oauth_callback_router.get("/callback")
def callback(state: str, code: str, db: Session = Depends(get_db)):
    state_hash = hashlib.sha256(state.encode()).hexdigest()
    record = db.scalar(select(CalendarOAuthState).where(
        CalendarOAuthState.state_hash == state_hash,
        CalendarOAuthState.consumed_at.is_(None),
        CalendarOAuthState.expires_at > datetime.now(timezone.utc),
    ).with_for_update())
    if not record:
        raise HTTPException(status_code=400, detail="Calendar OAuth state is invalid or expired")
    owner = db.get(User, record.user_id)
    if not owner or not owner.is_active or not owner.is_verified or owner.role != "candidate":
        raise HTTPException(status_code=403, detail="Calendar account owner is not authorized")
    record.consumed_at = datetime.now(timezone.utc)
    db.commit()
    try:
        flow = _flow(state)
        _CALENDAR_BREAKER.call(flow.fetch_token, code=code)
        credentials = flow.credentials
        serialized = credentials.to_json()
        account = db.scalar(select(CalendarAccount).where(
            CalendarAccount.user_id == record.user_id,
            CalendarAccount.provider == "google",
        ))
        if account is None:
            account = CalendarAccount(
                user_id=record.user_id, provider="google", email="",
                encrypted_credentials=encrypt_credential(serialized, purpose="google-calendar"),
                scopes=SCOPES,
            )
            db.add(account)
        else:
            account.encrypted_credentials = encrypt_credential(
                serialized, purpose="google-calendar",
            )
            account.scopes = SCOPES
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Google Calendar authorization could not be completed") from exc
    return RedirectResponse(get_settings().web_app_url + "/settings?calendar=connected")


@router.get("/account")
def account(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(CalendarAccount).where(
        CalendarAccount.user_id == user.id, CalendarAccount.provider == "google",
    ))
    return {"connected": bool(row), "email": row.email if row else "",
            "scopes": row.scopes if row else [], "provider": "google"}


def _calendar_event(interview: Interview, application: Application | None) -> dict:
    if interview.scheduled_at is None or interview.scheduled_at.tzinfo is None:
        raise HTTPException(status_code=422, detail="Set an explicit interview date, time and timezone first")
    duration = max(15, min(int(interview.duration_minutes or 30), 240))
    start = interview.scheduled_at
    end = start + timedelta(minutes=duration)
    role = application.role_title if application else "Job interview"
    company = application.company_name if application else ""
    event_id = hashlib.sha256(f"jobseeker:interview:{interview.id}".encode()).hexdigest()[:32]
    return {
        "id": event_id,
        "summary": f"{role} interview" + (f" · {company}" if company else ""),
        "description": (interview.notes or "")[:4000],
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": end.isoformat()},
        "transparency": "opaque",
    }


@router.post("/interviews/{interview_id}/sync")
def sync_interview_to_calendar(
    interview_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_rate_limit(f"calendar-sync:{user.id}", limit=30, window_seconds=3600)
    interview = db.scalar(select(Interview).where(
        Interview.id == interview_id, Interview.user_id == user.id,
    ).with_for_update())
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    application = None
    if interview.application_id:
        application = db.scalar(select(Application).where(
            Application.id == interview.application_id, Application.user_id == user.id,
        ))
    account_row = db.scalar(select(CalendarAccount).where(
        CalendarAccount.user_id == user.id, CalendarAccount.provider == "google",
    ))
    if not account_row:
        raise HTTPException(status_code=409, detail="Connect Google Calendar before syncing interviews")
    try:
        raw = decrypt_credential(account_row.encrypted_credentials, purpose="google-calendar")
        if credential_needs_rotation(account_row.encrypted_credentials):
            account_row.encrypted_credentials = rewrap_credential(
                account_row.encrypted_credentials, purpose="google-calendar",
            )
        credentials = Credentials.from_authorized_user_info(__import__("json").loads(raw), SCOPES)
        if credentials.expired and credentials.refresh_token:
            _CALENDAR_BREAKER.call(credentials.refresh, Request())
            account_row.encrypted_credentials = encrypt_credential(
                credentials.to_json(), purpose="google-calendar",
            )
            db.flush()
        if not credentials.valid:
            raise RuntimeError("Google Calendar authorization expired; reconnect the calendar")
        service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
        body = _calendar_event(interview, application)
        # Deterministic Google event IDs make retries safe even if Google created
        # the event but the local transaction failed before persisting its ID.
        event_id = interview.calendar_event_id or body["id"]
        try:
            response = _CALENDAR_BREAKER.call(
                service.events().update(
                    calendarId="primary", eventId=event_id, body=body,
                ).execute,
            )
        except HttpError as google_error:
            if getattr(getattr(google_error, "resp", None), "status", None) != 404:
                raise
            response = _CALENDAR_BREAKER.call(
                service.events().insert(calendarId="primary", body=body).execute,
            )
        interview.calendar_event_id = response.get("id", event_id)
        db.add(AuditLog(
            user_id=user.id, action="calendar.interview_synced",
            resource_type="interview", resource_id=str(interview.id),
        ))
        db.commit()
        return {"status": "synced", "interview_id": interview.id,
                "calendar_event_id": interview.calendar_event_id,
                "html_link": response.get("htmlLink", "")}
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail="Google Calendar sync failed; retry after checking the connection") from exc
