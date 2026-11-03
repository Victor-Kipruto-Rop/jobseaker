import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from packages.database.models import Base
from packages.database.models.career import AuditLog
from packages.database.models.identity import User
from packages.security.rbac import set_user_role


def test_operator_role_assignment_is_audited_and_can_be_revoked():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            user = User(
                email="role-target@example.com", password_hash="unused", is_active=True,
                is_verified=True,
            )
            db.add(user)
            db.commit()

            promoted = set_user_role(
                db,
                email=user.email,
                role="admin",
                operator="security-reviewer",
            )
            assert promoted.role == "admin"

            event = db.scalar(select(AuditLog).where(
                AuditLog.action == "security.role_changed",
                AuditLog.resource_id == str(user.id),
            ))
            assert event is not None
            assert event.user_id is None
            assert event.metadata_json == {
                "operator": "security-reviewer",
                "previous_role": "candidate",
                "new_role": "admin",
            }

            demoted = set_user_role(
                db,
                email=user.email,
                role="candidate",
                operator="security-reviewer",
            )
            assert demoted.role == "candidate"
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_operator_role_assignment_rejects_unknown_roles_and_accounts():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            with pytest.raises(ValueError):
                set_user_role(db, email="x@example.com", role="superuser", operator="operator")
            with pytest.raises(LookupError):
                set_user_role(db, email="missing@example.com", role="admin", operator="operator")
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
