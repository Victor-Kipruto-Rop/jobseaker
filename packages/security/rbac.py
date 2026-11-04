from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database.models.career import AuditLog
from packages.database.models.identity import User

ALLOWED_ROLES = frozenset({"candidate", "admin"})


def set_user_role(
    db: Session,
    *,
    email: str,
    role: str,
    operator: str,
) -> User:
    normalized_role = role.strip().lower()
    normalized_email = email.strip().lower()
    operator_name = operator.strip()
    if normalized_role not in ALLOWED_ROLES:
        raise ValueError("Role must be candidate or admin")
    if not normalized_email or not operator_name:
        raise ValueError("A target email and operator identity are required")

    user = db.scalar(select(User).where(User.email == normalized_email).with_for_update())
    if not user:
        raise LookupError("Target account was not found")

    if normalized_role == "admin" and (not user.is_active or not user.is_verified):
        raise ValueError("Administrator accounts must be active and email-verified")

    previous_role = user.role
    if previous_role == normalized_role:
        return user

    user.role = normalized_role
    db.add(
        AuditLog(
            user_id=None,
            action="security.role_changed",
            resource_type="user",
            resource_id=str(user.id),
            metadata_json={
                "operator": operator_name,
                "previous_role": previous_role,
                "new_role": normalized_role,
            },
        )
    )
    db.commit()
    db.refresh(user)
    return user
