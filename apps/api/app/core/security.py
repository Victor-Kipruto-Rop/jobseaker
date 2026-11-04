import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database.models.identity import User, UserSession

_password_hash = PasswordHash.recommended()
SESSION_TTL_HOURS = 24 * 7


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Password must contain at least 12 characters")
    return _password_hash.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    try:
        return _password_hash.verify(password, encoded)
    except Exception:  # noqa: BLE001 - malformed or unsupported stored hashes must fail closed.
        return False


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def create_session(db: Session, user: User) -> tuple[str, str, datetime]:
    token = secrets.token_urlsafe(48)
    csrf = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)
    db.add(UserSession(user_id=user.id, token_hash=_digest(token), csrf_hash=_digest(csrf), expires_at=expires))
    db.commit()
    return token, csrf, expires


def resolve_session(db: Session, token: str | None) -> tuple[User, UserSession] | None:
    if not token:
        return None
    session = db.scalar(select(UserSession).where(
        UserSession.token_hash == _digest(token),
        UserSession.revoked_at.is_(None),
        UserSession.expires_at > datetime.now(timezone.utc),
    ))
    if not session:
        return None
    user = db.get(User, session.user_id)
    if not user or not user.is_active:
        return None
    return user, session


def revoke_session(db: Session, session: UserSession) -> None:
    session.revoked_at = datetime.now(timezone.utc)
    db.commit()
