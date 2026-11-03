import pytest
from fastapi import HTTPException

from apps.api.app.api.v1.auth.routes import RegisterRequest
from apps.api.app.dependencies import require_roles
from packages.database.models.identity import User


def test_new_user_model_defaults_to_candidate_role():
    assert User.__table__.c.role.default.arg == "candidate"
    assert User.__table__.c.role.server_default.arg == "candidate"


def test_registration_payload_cannot_assign_privileged_role():
    body = RegisterRequest.model_validate({
        "email": "candidate@example.com",
        "password": "long-enough-password",
        "full_name": "Candidate User",
        "role": "admin",
    })
    assert not hasattr(body, "role")


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
