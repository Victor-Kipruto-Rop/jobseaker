from fastapi.routing import APIRoute

from apps.api.app.main import app


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
    missing = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/api/v1/"):
            continue
        if route.path in PUBLIC_TOKEN_ROUTES | MANUALLY_AUTHENTICATED_ROUTES | STATE_AUTHENTICATED_ROUTES:
            continue
        calls = _dependency_calls(route.dependant)
        names = {getattr(call, "__name__", "") for call in calls}
        if not any(name.startswith("get_current_user") for name in names):
            missing.append(f"{','.join(sorted(route.methods or []))} {route.path}")
    assert not missing, "API routes missing an explicit authentication boundary: " + ", ".join(missing)


def test_every_candidate_resource_route_enforces_candidate_role_policy():
    missing = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/api/v1/"):
            continue
        if route.path in PUBLIC_TOKEN_ROUTES | MANUALLY_AUTHENTICATED_ROUTES | STATE_AUTHENTICATED_ROUTES:
            continue
        if route.path.startswith("/api/v1/auth/"):
            continue
        calls = _dependency_calls(route.dependant)
        role_policies = [getattr(call, "required_roles", None) for call in calls]
        if frozenset({"candidate"}) not in role_policies:
            missing.append(f"{','.join(sorted(route.methods or []))} {route.path}")
    assert not missing, "Candidate endpoints missing candidate-role policy: " + ", ".join(missing)


def test_candidate_api_rejects_administrator_and_accepts_candidate_sessions():
    from fastapi.testclient import TestClient
    from apps.api.app.dependencies import get_current_user
    from packages.database.models.identity import User

    admin = User(email="route-admin@example.com", password_hash="unused", role="admin")
    candidate = User(email="route-candidate@example.com", password_hash="unused", role="candidate")
    try:
        app.dependency_overrides[get_current_user] = lambda: admin
        with TestClient(app) as client:
            denied = client.get("/api/v1/profile")
            assert denied.status_code == 403
            assert denied.json()["detail"] == "Insufficient permissions"

        app.dependency_overrides[get_current_user] = lambda: candidate
        with TestClient(app) as client:
            allowed = client.get("/api/v1/profile")
            assert allowed.status_code == 200
    finally:
        app.dependency_overrides.pop(get_current_user, None)
