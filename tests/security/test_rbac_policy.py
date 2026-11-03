import pytest
from fastapi import HTTPException

from apps.api.app.api.v1.auth.routes import RegisterRequest
from apps.api.app.dependencies import require_roles
from packages.database.models.identity import User


def test_new_user_model_defaults_to_candidate_role():
    assert User.__table__.c.role.default.arg == "candidate"
    assert User.__table__.c.role.server_default.arg == "candidate"


def test_registration_payload_cannot_assign_privileged_role():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        RegisterRequest.model_validate({
            "email": "candidate@example.com",
            "password": "long-enough-password",
            "full_name": "Candidate User",
            "role": "admin",
        })


def test_candidate_is_denied_admin_policy():
    candidate = User(
        email="candidate@example.com",
        password_hash="unused",
        role="candidate",
    )
    admin_guard = require_roles("admin")
    with pytest.raises(HTTPException) as error:
        admin_guard(candidate)
    assert error.value.status_code == 403


def test_admin_is_allowed_admin_policy():
    admin = User(
        email="admin@example.com",
        password_hash="unused",
        role="admin",
    )
    assert require_roles("admin")(admin) is admin


def test_role_policy_rejects_unknown_or_empty_roles():
    with pytest.raises(ValueError):
        require_roles()
    with pytest.raises(ValueError):
        require_roles("superuser")



def test_administrator_is_denied_candidate_only_policy():
    admin = User(
        email="admin@example.com",
        password_hash="unused",
        role="admin",
    )
    candidate_guard = require_roles("candidate")
    with pytest.raises(HTTPException) as error:
        candidate_guard(admin)
    assert error.value.status_code == 403


def test_role_model_rejects_unknown_database_roles():
    from sqlalchemy import create_engine
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session
    from packages.database.models import Base

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            db.add(User(
                email="invalid-role@example.com",
                password_hash="unused",
                role="superuser",
            ))
            with pytest.raises(IntegrityError):
                db.commit()
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
