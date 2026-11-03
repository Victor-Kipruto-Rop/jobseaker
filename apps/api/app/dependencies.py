from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from packages.database.sessions import SessionLocal
from packages.database.models.identity import User
from apps.api.app.core.security import resolve_session

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    result = resolve_session(db, request.cookies.get("jobseeker_session"))
    if not result:
        raise HTTPException(status_code=401, detail="Authentication required")
    return result[0]

def get_verified_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Verify your email address before connecting external accounts")
    return user


def require_roles(*allowed_roles: str):
    """Build a centralized role guard; ownership checks remain separate and mandatory."""
    normalized = frozenset(role.strip().lower() for role in allowed_roles if role.strip())
    if not normalized or not normalized.issubset({"candidate", "admin"}):
        raise ValueError("Authorization policy must specify one or more supported roles")

    def role_guard(user: User = Depends(get_current_user)) -> User:
        if user.role not in normalized:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    role_guard.required_roles = normalized
    role_guard.__name__ = "role_guard_" + "_".join(sorted(normalized))
    return role_guard
