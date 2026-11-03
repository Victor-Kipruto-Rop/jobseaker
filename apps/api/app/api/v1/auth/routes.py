import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from apps.api.app.dependencies import get_db, get_current_user
from apps.api.app.core.config import get_settings
from apps.api.app.core.redis_limits import enforce_rate_limit
from apps.api.app.core.security import create_session, hash_password, resolve_session, revoke_session, verify_password
from packages.database.models.identity import User, UserSession
from packages.database.models.career import AuditLog, CandidateProfile, AccountToken
from packages.integrations.email.smtp import configured, send_transactional_email

router = APIRouter()
COOKIE_NAME = "jobseeker_session"
CSRF_COOKIE = "jobseeker_csrf"

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    full_name: str = Field(min_length=2, max_length=160)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

def _set_session(response: Response, token: str, csrf: str, expires: datetime) -> None:
    secure = get_settings().app_env == "production"
    response.set_cookie(COOKIE_NAME, token, httponly=True, secure=secure, samesite="lax",
                        expires=expires, path="/")
    response.set_cookie(CSRF_COOKIE, csrf, httponly=False, secure=secure, samesite="lax",
                        expires=expires, path="/")

def _current(request: Request, db: Session):
    result = resolve_session(db, request.cookies.get(COOKIE_NAME))
    if not result:
        raise HTTPException(status_code=401, detail="Authentication required")
    return result

@router.get("/csrf")
def csrf(request: Request, response: Response, db: Session = Depends(get_db)):
    import secrets
    if request.cookies.get(COOKIE_NAME) and resolve_session(db, request.cookies.get(COOKIE_NAME)):
        return {"authenticated": True, "csrf_token": "session-cookie-preserved"}
    value = secrets.token_urlsafe(32)
    response.set_cookie(CSRF_COOKIE, value, httponly=False,
                        secure=get_settings().app_env == "production", samesite="lax", path="/")
    return {"csrf_token": value}

@router.post("/register", status_code=201)
def register(body: RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    enforce_rate_limit(f"register:{request.client.host if request.client else 'unknown'}", 5, 3600)
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(email=email, password_hash=hash_password(body.password), full_name=body.full_name.strip())
    db.add(user)
    db.flush()
    db.add(CandidateProfile(user_id=user.id))
    db.add(AuditLog(user_id=user.id, action="account.registered"))
    db.commit()
    token, csrf_token, expires = create_session(db, user)
    _set_session(response, token, csrf_token, expires)
    return {"id": user.id, "email": user.email, "full_name": user.full_name, "is_verified": user.is_verified}

@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    enforce_rate_limit(f"login-ip:{request.client.host if request.client else 'unknown'}", 30, 300)
    email_key = hashlib.sha256(body.email.lower().encode("utf-8")).hexdigest()
    enforce_rate_limit(f"login-email:{email_key}", 10, 300)
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not verify_password(body.password, user.password_hash) or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token, csrf_token, expires = create_session(db, user)
    db.add(AuditLog(user_id=user.id, action="account.login"))
    db.commit()
    _set_session(response, token, csrf_token, expires)
    return {"id": user.id, "email": user.email, "full_name": user.full_name, "is_verified": user.is_verified}

@router.get("/me")
def me(request: Request, db: Session = Depends(get_db)):
    user, _ = _current(request, db)
    return {"id": user.id, "email": user.email, "full_name": user.full_name, "is_verified": user.is_verified}

@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    user, session = _current(request, db)
    revoke_session(db, session)
    db.add(AuditLog(user_id=user.id, action="account.logout"))
    db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    return {"status": "signed_out"}

class TokenConfirm(BaseModel):
    token: str = Field(min_length=20, max_length=200)

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=12, max_length=128)

def _new_account_token(db: Session, user: User, purpose: str, lifetime: timedelta) -> str:
    now = datetime.now(timezone.utc)
    db.execute(update(AccountToken).where(
        AccountToken.user_id == user.id, AccountToken.purpose == purpose,
        AccountToken.consumed_at.is_(None)).values(consumed_at=now))
    token = secrets.token_urlsafe(36)
    db.add(AccountToken(user_id=user.id, purpose=purpose,
        token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
        expires_at=now + lifetime))
    db.commit()
    return token

def _consume_account_token(db: Session, raw_token: str, purpose: str):
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    record = db.scalar(select(AccountToken).where(
        AccountToken.token_hash == token_hash, AccountToken.purpose == purpose,
        AccountToken.consumed_at.is_(None),
        AccountToken.expires_at > datetime.now(timezone.utc)))
    if not record:
        raise HTTPException(status_code=400, detail="Token is invalid, expired, or already used")
    record.consumed_at = datetime.now(timezone.utc)
    return record

@router.post("/verification/request")
def request_verification(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.is_verified:
        return {"status": "already_verified"}
    enforce_rate_limit(f"verify-email:{user.id}", 3, 3600)
    if not configured() and get_settings().app_env == "production":
        raise HTTPException(status_code=503, detail="Transactional email delivery is not configured")
    token = _new_account_token(db, user, "email_verification", timedelta(hours=24))
    link = get_settings().web_app_url + "/verify-email?token=" + token
    sent = send_transactional_email(user.email, "Verify your JobSeeker account",
                                    "Verify your email address using this link: " + link)
    if not sent:
        if get_settings().app_env == "production":
            _consume_account_token(db, token, "email_verification")
            db.commit()
            raise HTTPException(status_code=503, detail="Verification email could not be delivered")
        return {"status": "created_local", "debug_token": token}
    return {"status": "sent"}

@router.post("/verification/confirm")
def confirm_verification(body: TokenConfirm, db: Session = Depends(get_db)):
    record = _consume_account_token(db, body.token, "email_verification")
    user = db.get(User, record.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Account not found")
    user.is_verified = True
    db.add(AuditLog(user_id=user.id, action="account.email_verified"))
    db.commit()
    return {"status": "verified"}

@router.post("/password-reset/request", status_code=202)
def request_password_reset(body: PasswordResetRequest, request: Request,
                           db: Session = Depends(get_db)):
    enforce_rate_limit(f"password-reset-ip:{request.client.host if request.client else 'unknown'}", 10, 3600)
    email_key = hashlib.sha256(body.email.lower().encode("utf-8")).hexdigest()
    enforce_rate_limit(f"password-reset-email:{email_key}", 3, 3600)
    if not configured() and get_settings().app_env == "production":
        raise HTTPException(status_code=503, detail="Transactional email delivery is not configured")
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user:
        return {"status": "accepted"}
    token = _new_account_token(db, user, "password_reset", timedelta(minutes=30))
    link = get_settings().web_app_url + "/reset-password?token=" + token
    sent = send_transactional_email(user.email, "Reset your JobSeeker password",
                                    "Use this link within 30 minutes to reset your password: " + link)
    if not sent:
        if get_settings().app_env == "production":
            _consume_account_token(db, token, "password_reset")
            db.commit()
        # Never disclose reset tokens in production or reveal account existence.
        return {"status": "accepted"}
    return {"status": "accepted"}

@router.post("/password-reset/confirm")
def confirm_password_reset(body: PasswordResetConfirm, db: Session = Depends(get_db)):
    record = _consume_account_token(db, body.token, "password_reset")
    user = db.get(User, record.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="Account not found")
    user.password_hash = hash_password(body.new_password)
    now = datetime.now(timezone.utc)
    db.execute(update(UserSession).where(UserSession.user_id == user.id,
        UserSession.revoked_at.is_(None)).values(revoked_at=now))
    db.add(AuditLog(user_id=user.id, action="account.password_reset"))
    db.commit()
    return {"status": "password_reset", "sessions_revoked": True}
