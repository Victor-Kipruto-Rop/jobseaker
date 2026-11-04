import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from cryptography.fernet import Fernet, InvalidToken
from packages.security.credential_vault import encrypt_credential, decrypt_credential
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from apps.api.app.core.config import get_settings
from packages.database.models.career import OAuthState, EmailAccount, EmailMessage
from packages.database.models.identity import User

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
JOB_QUERY = "in:anywhere {subject:job subject:career subject:vacancy subject:application subject:interview subject:recruitment subject:recruiter}"

def _fernet():
    secret = get_settings().app_secret_key.encode("utf-8")
    key = __import__("base64").urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)

def _encrypt(value: str) -> str:
    return encrypt_credential(value, purpose="gmail-oauth")

def _decrypt(value: str) -> str:
    if value.startswith("v1:"):
        try:
            return decrypt_credential(value, purpose="gmail-oauth")
        except Exception as exc:
            raise RuntimeError("Stored Gmail credentials cannot be decrypted. Check the credential key.") from exc
    # Read-only compatibility for existing Fernet ciphertexts. The next successful
    # sync rewrites the token using the dedicated credential key.
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("Stored Gmail credentials cannot be decrypted. Check credential key configuration.") from exc

def _flow(state: str | None = None):
    settings = get_settings()
    if not settings.gmail_enabled or not settings.gmail_client_secret_file:
        raise RuntimeError("Configure GMAIL_ENABLED and GMAIL_CLIENT_SECRET_FILE first.")
    flow = Flow.from_client_secrets_file(settings.gmail_client_secret_file, scopes=SCOPES, state=state)
    flow.redirect_uri = settings.gmail_redirect_uri
    return flow

def create_authorization(db: Session, user_id: int) -> str:
    owner = db.get(User, user_id)
    if not owner or not owner.is_active or not owner.is_verified or owner.role != "candidate":
        raise ValueError("Only active, verified candidate accounts can connect Gmail.")

    # Validate OAuth configuration and construct the URL before persisting state.
    # A missing client-secret file must not leave orphaned, apparently valid states.
    state = secrets.token_urlsafe(32)
    flow = _flow(state)
    url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    db.add(OAuthState(
        user_id=user_id,
        state_hash=hashlib.sha256(state.encode()).hexdigest(),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    ))
    db.commit()
    return url

def complete_authorization(db: Session, state: str, code: str) -> EmailAccount:
    state_hash = hashlib.sha256(state.encode()).hexdigest()
    record = db.scalar(select(OAuthState).where(
        OAuthState.state_hash == state_hash, OAuthState.consumed_at.is_(None),
        OAuthState.expires_at > datetime.now(timezone.utc)).with_for_update())
    if not record:
        raise ValueError("OAuth state is invalid, expired, or already used.")
    owner = db.get(User, record.user_id)
    if not owner or not owner.is_active or not owner.is_verified or owner.role != "candidate":
        raise ValueError("OAuth state owner is not authorized to connect Gmail.")
    # Consume the state before calling Google so concurrent callbacks cannot replay it.
    record.consumed_at = datetime.now(timezone.utc)
    db.commit()
    flow = _flow(state)
    flow.fetch_token(code=code)
    credentials = flow.credentials
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    mailbox = service.users().getProfile(userId="me").execute().get("emailAddress", "").lower()
    if not mailbox:
        raise RuntimeError("Google did not return a Gmail mailbox address.")
    serialized = credentials.to_json()
    account = db.scalar(select(EmailAccount).where(
        EmailAccount.user_id == record.user_id, EmailAccount.provider == "gmail"))
    if not account:
        account = EmailAccount(user_id=record.user_id, provider="gmail", email=mailbox,
                               encrypted_credentials=_encrypt(serialized), scopes=SCOPES)
        db.add(account)
    else:
        account.email = mailbox
        account.encrypted_credentials = _encrypt(serialized)
        account.scopes = SCOPES
    db.commit()
    db.refresh(account)
    return account

def classify(subject: str, snippet: str) -> tuple[str, float, bool]:
    text = f"{subject} {snippet}".lower()
    rules = [
        ("interview_invitation", ("interview", "schedule a call", "availability for a call"), True),
        ("assessment_request", ("assessment", "technical test", "coding test", "take-home"), True),
        ("rejection", ("unfortunately", "not be moving forward", "not selected", "regret to inform"), False),
        ("offer_or_salary", ("offer letter", "salary expectation", "compensation package"), True),
        ("information_request", ("please provide", "could you share", "additional information"), True),
        ("acknowledgement", ("application received", "thank you for applying", "we have received"), False),
    ]
    for category, phrases, action in rules:
        if any(phrase in text for phrase in phrases):
            return category, 0.8, action
    return "unclassified_job_related", 0.25, False

def sync_messages(db: Session, user_id: int, limit: int = 200) -> dict:
    account = db.scalar(select(EmailAccount).where(
        EmailAccount.user_id == user_id, EmailAccount.provider == "gmail"))
    if not account:
        raise LookupError("Connect a Gmail account before synchronizing.")
    raw = _decrypt(account.encrypted_credentials)
    if not account.encrypted_credentials.startswith("v1:"):
        account.encrypted_credentials = _encrypt(raw)
    credentials = Credentials.from_authorized_user_info(json.loads(raw), SCOPES)
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        account.encrypted_credentials = _encrypt(credentials.to_json())
    if not credentials.valid:
        raise RuntimeError("Gmail authorization expired. Reconnect the account.")
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    listed, inserted, page_token = 0, 0, None
    while listed < limit:
        result = service.users().messages().list(
            userId="me", q=JOB_QUERY, maxResults=min(100, limit-listed),
            pageToken=page_token).execute()
        messages = result.get("messages", [])
        for item in messages:
            message_id = item["id"]
            exists = db.scalar(select(EmailMessage.id).where(
                EmailMessage.account_id == account.id,
                EmailMessage.gmail_message_id == message_id))
            if exists:
                continue
            metadata = service.users().messages().get(
                userId="me", id=message_id, format="metadata",
                metadataHeaders=["From", "To", "Subject"]).execute()
            headers = {h.get("name", "").lower(): h.get("value", "")
                       for h in metadata.get("payload", {}).get("headers", [])}
            subject, snippet = headers.get("subject", ""), metadata.get("snippet", "")
            classification, confidence, action = classify(subject, snippet)
            internal_date = metadata.get("internalDate")
            received = datetime.fromtimestamp(int(internal_date)/1000, tz=timezone.utc) if internal_date else None
            db.add(EmailMessage(user_id=user_id, account_id=account.id,
                gmail_message_id=message_id, gmail_thread_id=metadata.get("threadId", ""),
                sender=headers.get("from", "")[:320], recipient=headers.get("to", "")[:320],
                subject=subject[:1000], snippet=snippet[:5000], classification=classification,
                confidence=confidence, action_required=action, received_at=received))
            inserted += 1
        listed += len(messages)
        page_token = result.get("nextPageToken")
        if not page_token or not messages:
            break
    account.last_synced_at = datetime.now(timezone.utc)
    db.commit()
    return {"mailbox": account.email, "listed": listed, "new_messages": inserted,
            "query": JOB_QUERY, "read_only": True}
