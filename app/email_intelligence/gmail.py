from datetime import datetime, timezone
from email.utils import parseaddr

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import EmailEvent, GmailSyncState, RecruiterFeedback, SourceImportRow

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
DEFAULT_QUERY = "in:anywhere {subject:job subject:career subject:vacancy subject:application subject:interview subject:recruitment}"


def get_gmail_service():
    settings = get_settings()
    if not settings.gmail_enabled:
        raise RuntimeError("GMAIL_ENABLED must be true before starting Gmail sync.")
    if not settings.gmail_client_secret_file or not settings.gmail_token_file:
        raise RuntimeError("Set GMAIL_CLIENT_SECRET_FILE and GMAIL_TOKEN_FILE before Gmail sync.")
    token_path = settings.gmail_token_file
    try:
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    except (OSError, ValueError):
        creds = None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(settings.gmail_client_secret_file, SCOPES)
            creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
        with open(token_path, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _headers(message):
    return {item.get("name", "").lower(): item.get("value", "")
            for item in message.get("payload", {}).get("headers", [])}


def classify_message(subject: str, snippet: str) -> tuple[str, float, bool, str]:
    text = f"{subject} {snippet}".lower()
    rules = [
        ("interview_invitation", ("interview", "schedule a call", "availability for a call"), True),
        ("assessment_request", ("assessment", "technical test", "coding test", "take-home"), True),
        ("rejection", ("unfortunately", "not be moving forward", "not selected", "regret to inform"), False),
        ("offer_or_salary", ("offer letter", "salary expectation", "compensation package"), True),
        ("information_request", ("please provide", "could you share", "additional information"), True),
        ("acknowledgement", ("application received", "thank you for applying", "we have received"), False),
        ("bounce", ("delivery status notification", "address not found", "undelivered mail"), True),
    ]
    for category, phrases, action in rules:
        for phrase in phrases:
            if phrase in text:
                return category, 0.72, action, phrase
    return "unclassified_job_related", 0.25, False, "No deterministic classification phrase matched"


def _store_message(db: Session, message: dict, mailbox: str):
    message_id = message.get("id")
    if not message_id or db.scalar(select(EmailEvent.id).where(EmailEvent.gmail_message_id == message_id)):
        return False
    headers = _headers(message)
    subject = headers.get("subject", "")
    snippet = message.get("snippet", "")
    category, confidence, action, evidence = classify_message(subject, snippet)
    sender = parseaddr(headers.get("from", ""))[1].lower()
    direction = "outbound" if sender == mailbox.lower() else "inbound"
    internal_date = message.get("internalDate")
    received_at = datetime.fromtimestamp(int(internal_date) / 1000, tz=timezone.utc) if internal_date else None
    thread_id = message.get("threadId")
    db.add(EmailEvent(
        gmail_message_id=message_id,
        gmail_thread_id=thread_id,
        direction=direction,
        classification=category,
        classification_confidence=confidence,
        received_at=received_at,
    ))
    if direction == "inbound":
        db.add(RecruiterFeedback(
            gmail_message_id=message_id,
            gmail_thread_id=thread_id,
            category=category,
            confidence=confidence,
            evidence=f"Matched phrase: {evidence}; subject: {subject[:300]}",
            action_required=action,
        ))
    return True


def sync_job_related_mail(db: Session, *, query: str = DEFAULT_QUERY, max_messages: int = 500):
    """Read metadata/snippets only. Never sends, marks read, archives, or deletes mail."""
    service = get_gmail_service()
    profile = service.users().getProfile(userId="me").execute()
    mailbox = profile.get("emailAddress", "").lower()
    if not mailbox:
        raise RuntimeError("Gmail profile did not return a mailbox address.")

    state = db.scalar(select(GmailSyncState).where(GmailSyncState.mailbox == mailbox))
    if state is None:
        state = GmailSyncState(mailbox=mailbox, sync_status="running")
        db.add(state)
        db.flush()
    state.sync_status = "running"
    state.last_query = query

    message_ids = set()
    for row in db.scalars(select(SourceImportRow).where(SourceImportRow.gmail_message_id.is_not(None))):
        message_ids.add(row.gmail_message_id)

    page_token = None
    listed = 0
    while listed < max_messages:
        response = service.users().messages().list(
            userId="me", q=query, maxResults=min(100, max_messages - listed),
            pageToken=page_token
        ).execute()
        items = response.get("messages", [])
        for item in items:
            message_ids.add(item["id"])
        listed += len(items)
        page_token = response.get("nextPageToken")
        if not page_token or not items:
            break

    fetched = 0
    inserted = 0
    failures = []
    for message_id in message_ids:
        if db.scalar(select(EmailEvent.id).where(EmailEvent.gmail_message_id == message_id)):
            continue
        try:
            message = service.users().messages().get(
                userId="me", id=message_id, format="metadata",
                metadataHeaders=["From", "To", "Subject", "Date"]
            ).execute()
            inserted += int(_store_message(db, message, mailbox))
            fetched += 1
        except Exception as exc:
            failures.append({"message_id": message_id, "error": str(exc)[:250]})

    state.last_synced_at = datetime.now(timezone.utc)
    state.sync_status = "completed_with_errors" if failures else "completed"
    state.last_error = f"{len(failures)} message fetch failures" if failures else None
    db.commit()
    seeded = db.scalar(select(__import__("sqlalchemy").func.count()).select_from(SourceImportRow).where(
        SourceImportRow.gmail_message_id.is_not(None)
    )) or 0
    return {"mailbox": mailbox, "query": query, "unique_message_ids": len(message_ids | set(thread_messages)),\n            "threads_checked": len(thread_ids),
            "fetched": fetched, "new_events": inserted, "seeded_outreach_ids": seeded,
            "fetch_failures": failures}
