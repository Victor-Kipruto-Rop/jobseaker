from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from apps.api.app.dependencies import get_db
from apps.api.app.core.config import get_settings
from apps.api.app.core.redis_limits import enforce_rate_limit
from apps.api.app.core.security import create_session, hash_password, resolve_session, revoke_session, verify_password
from packages.database.models.identity import User
from packages.database.models.career import AuditLog, CandidateProfile

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
def csrf(response: Response):
    import secrets
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
    enforce_rate_limit(f"login:{request.client.host if request.client else 'unknown'}", 10, 300)
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
