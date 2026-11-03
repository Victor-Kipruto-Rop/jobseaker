import pytest
from fastapi.testclient import TestClient

from apps.api.app.main import app


@pytest.fixture
def client():
    yield TestClient(app)


def test_anonymous_mutation_rejects_missing_csrf_handshake(client):
    response = client.post("/api/v1/auth/login", json={}, headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF validation failed"


def test_anonymous_mutation_rejects_mismatched_csrf_values(client):
    response = client.post(
        "/api/v1/auth/login",
        json={},
        cookies={"jobseeker_csrf": "cookie-token"},
        headers={"X-CSRF-Token": "different-token", "Origin": "http://localhost:3000"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF validation failed"


def test_anonymous_mutation_passes_csrf_boundary_with_matching_values(client):
    response = client.post(
        "/api/v1/auth/login",
        json={},
        cookies={"jobseeker_csrf": "matching-token"},
        headers={"X-CSRF-Token": "matching-token", "Origin": "http://localhost:3000"},
    )
    # The empty login payload is rejected by FastAPI validation only after
    # the real ASGI CSRF middleware has accepted the request.
    assert response.status_code == 422


def test_mutation_rejects_untrusted_origin_even_with_valid_csrf_token(client):
    response = client.post(
        "/api/v1/auth/login",
        json={},
        cookies={"jobseeker_csrf": "matching-token"},
        headers={
            "X-CSRF-Token": "matching-token",
            "Origin": "https://attacker.example",
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Untrusted request origin"


def test_mutation_rejects_cross_site_fetch_metadata_even_with_valid_csrf_token(client):
    response = client.post(
        "/api/v1/auth/login",
        json={},
        cookies={"jobseeker_csrf": "matching-token"},
        headers={
            "X-CSRF-Token": "matching-token",
            "Origin": "http://localhost:3000",
            "Sec-Fetch-Site": "cross-site",
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Cross-site state changes are not allowed"


def test_safe_get_does_not_require_csrf_token(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "JobSeeker Intelligence"


def test_real_csrf_bootstrap_token_is_accepted_by_anonymous_mutation(client):
    bootstrap = client.get("/api/v1/auth/csrf")
    assert bootstrap.status_code == 200
    token = bootstrap.json()["csrf_token"]
    response = client.post(
        "/api/v1/auth/login",
        json={},
        headers={"X-CSRF-Token": token, "Origin": "http://localhost:3000"},
    )
    assert response.status_code == 422


def test_authenticated_mutation_requires_session_bound_csrf_token(client, monkeypatch):
    import hashlib
    from types import SimpleNamespace
    from apps.api.app import main

    valid_token = "session-bound-csrf-token"
    expected_hash = hashlib.sha256(valid_token.encode("utf-8")).hexdigest()
    monkeypatch.setattr(
        main,
        "resolve_session",
        lambda db, token: (object(), SimpleNamespace(csrf_hash=expected_hash)),
    )
    accepted = client.post(
        "/api/v1/auth/login",
        json={},
        cookies={
            "jobseeker_session": "valid-session-token",
            "jobseeker_csrf": valid_token,
        },
        headers={"X-CSRF-Token": valid_token, "Origin": "http://localhost:3000"},
    )
    assert accepted.status_code == 422

    rejected = client.post(
        "/api/v1/auth/login",
        json={},
        cookies={
            "jobseeker_session": "valid-session-token",
            "jobseeker_csrf": "tampered-token",
        },
        headers={"X-CSRF-Token": "tampered-token", "Origin": "http://localhost:3000"},
    )
    assert rejected.status_code == 403
    assert rejected.json()["detail"] == "CSRF session binding failed"


def test_account_me_requires_a_valid_session(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"


def test_logout_requires_csrf_handshake_and_valid_session(client):
    response = client.post(
        "/api/v1/auth/logout",
        cookies={"jobseeker_csrf": "valid-double-submit"},
        headers={"X-CSRF-Token": "valid-double-submit", "Origin": "http://localhost:3000"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"


def test_gmail_oauth_callback_rejects_unknown_state_without_creating_a_session(client):
    response = client.get(
        "/api/v1/integrations/gmail/callback",
        params={
            "state": "unknown-state-token-long-enough-123456",
            "code": "authorization-code",
        },
    )
    assert response.status_code == 400



def test_mutation_rejects_missing_origin_even_with_matching_csrf_values(client):
    response = client.post(
        "/api/v1/auth/login",
        json={},
        cookies={"jobseeker_csrf": "matching-token"},
        headers={"X-CSRF-Token": "matching-token"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Request origin is required"
