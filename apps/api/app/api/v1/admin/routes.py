from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.dependencies import get_db, require_roles
from packages.database.models.career import AuditLog
from packages.database.models.identity import User

router = APIRouter()


@router.get("/users")
def list_users(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Return a minimal, paginated account directory without credentials or tokens."""
    rows = db.scalars(
        select(User).order_by(User.created_at.desc(), User.id.desc())
        .offset(offset).limit(limit)
    ).all()
    return [
        {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "created_at": user.created_at,
        }
        for user in rows
    ]


@router.get("/audit-logs")
def list_audit_logs(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user_id: int | None = Query(default=None, ge=1),
    action: str | None = Query(default=None, min_length=2, max_length=120),
    _: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Read-only, paginated security and account activity audit feed."""
    statement = select(AuditLog)
    if user_id is not None:
        statement = statement.where(AuditLog.user_id == user_id)
    if action:
        statement = statement.where(AuditLog.action == action)
    rows = db.scalars(
        statement.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset(offset).limit(limit)
    ).all()
    return [
        {
            "id": row.id,
            "user_id": row.user_id,
            "action": row.action,
            "resource_type": row.resource_type,
            "resource_id": row.resource_id,
            "created_at": row.created_at,
        }
        for row in rows
    ]
