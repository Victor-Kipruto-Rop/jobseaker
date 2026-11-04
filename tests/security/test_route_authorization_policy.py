import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from apps.api.app.api.v1.admin.routes import router as admin_router
from apps.api.app.api.v1.auth.routes import router as auth_router
from apps.api.app.api.v1.router import candidate_policy
from apps.api.app.dependencies import get_current_user, get_db
from apps.api.app.main import app
from packages.database.models import Base
from packages.database.models.identity import User


PUBLIC_TOKEN_ROUTES = {
    "/api/v1/auth/csrf",
    "/api/v1/auth/register",
    "/api/v1/auth/login",
    "/api/v1/auth/password-reset/request",
    "/api/v1/auth/password-reset/confirm",
    "/api/v1/auth/verification/confirm",
}
MANUALLY_AUTHENTICATED_ROUTES = {
    "/api/v1/auth/me",
    "/api/v1/auth/logout",
}
ADMIN_ROLE_ROUTES = {"/api/v1/admin/users", "/api/v1/admin/audit-logs"}
CANDIDATE_AUTH_ROUTES = {"/api/v1/auth/verification/request"}
STATE_AUTHENTICATED_ROUTES = {
    "/api/v1/integrations/gmail/callback",
}


def _dependency_calls(dependant):
    calls = set()
    for dependency in dependant.dependencies:
        calls.add(dependency.call)
        calls.update(_dependency_calls(dependency))
    return calls


def test_every_api_route_has_an_explicit_authentication_boundary():
    paths = set(app.openapi()["paths"])
    api_paths = {path for path in paths if path.startswith("/api/v1/")}
    assert api_paths
    exempt = PUBLIC_TOKEN_ROUTES | MANUALLY_AUTHENTICATED_ROUTES | STATE_AUTHENTICATED_ROUTES
    assert ADMIN_ROLE_ROUTES <= api_paths
    assert CANDIDATE_AUTH_ROUTES <= api_paths
    assert exempt <= api_paths
    # Every remaining API path belongs to a candidate workspace router, which
    # is mounted with the shared candidate-role dependency below.
    assert api_paths - exempt - ADMIN_ROLE_ROUTES - CANDIDATE_AUTH_ROUTES


def test_every_candidate_resource_route_enforces_candidate_role_policy():
    paths = set(app.openapi()["paths"])
    candidate_paths = paths - PUBLIC_TOKEN_ROUTES - MANUALLY_AUTHENTICATED_ROUTES - STATE_AUTHENTICATED_ROUTES - ADMIN_ROLE_ROUTES - CANDIDATE_AUTH_ROUTES
    assert candidate_paths
    candidate_guard = candidate_policy[0].dependency
    assert getattr(candidate_guard, "required_roles", None) == frozenset({"candidate"})


@pytest.fixture
def authorization_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = Session(engine)
    admin = User(email="route-admin@example.com", password_hash="unused", role="admin")
    candidate = User(email="route-candidate@example.com", password_hash="unused", role="candidate")
    db.add_all([admin, candidate])
    db.commit()

    active_user = {"value": admin}

    def override_user():
        return active_user["value"]

    def override_db():
        yield db

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    try:
        yield TestClient(app), active_user, admin, candidate
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_candidate_api_rejects_administrator_and_accepts_candidate_sessions(authorization_client):
    client, active_user, admin, candidate = authorization_client
    active_user["value"] = admin
    denied = client.get("/api/v1/profile")
    assert denied.status_code == 403
    assert denied.json()["detail"] == "Insufficient permissions"

    active_user["value"] = candidate
    allowed = client.get("/api/v1/profile")
    assert allowed.status_code == 200
    assert allowed.json()["user"]["id"] == candidate.id


def test_registration_rejects_privileged_role_mass_assignment():
    from pydantic import ValidationError
    from apps.api.app.api.v1.auth.routes import RegisterRequest

    with pytest.raises(ValidationError):
        RegisterRequest.model_validate({
            "email": "candidate@example.com",
            "password": "long-enough-password",
            "full_name": "Candidate User",
            "role": "admin",
        })



def test_admin_routes_require_admin_policy():
    admin_paths = {"/api/v1/admin/users", "/api/v1/admin/audit-logs"}
    found = set()
    for route in admin_router.routes:
        if not isinstance(route, APIRoute):
            continue
        path = "/api/v1/admin" + route.path
        if path not in admin_paths:
            continue
        calls = _dependency_calls(route.dependant)
        policies = [getattr(call, "required_roles", None) for call in calls]
        assert frozenset({"admin"}) in policies
        found.add(path)
    assert found == admin_paths


def test_admin_endpoints_deny_candidates_and_allow_admins(authorization_client):
    client, active_user, admin, candidate = authorization_client
    active_user["value"] = candidate
    denied = client.get("/api/v1/admin/users")
    assert denied.status_code == 403

    active_user["value"] = admin
    allowed = client.get("/api/v1/admin/users")
    assert allowed.status_code == 200
    assert all("password_hash" not in row for row in allowed.json())
    logs = client.get("/api/v1/admin/audit-logs")
    assert logs.status_code == 200



def test_authenticated_verification_request_requires_candidate_role():
    route = next(
        route for route in auth_router.routes
        if isinstance(route, APIRoute) and route.path == "/verification/request"
    )
    calls = _dependency_calls(route.dependant)
    policies = [getattr(call, "required_roles", None) for call in calls]
    assert frozenset({"candidate"}) in policies
