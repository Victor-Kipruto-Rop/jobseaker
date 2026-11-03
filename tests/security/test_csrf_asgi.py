from fastapi.testclient import TestClient

from apps.api.app.main import app


client = TestClient(app)


def test_anonymous_mutation_rejects_missing_csrf_handshake():
    response = client.post("/api/v1/auth/login", json={})
    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF validation failed"


def test_anonymous_mutation_rejects_mismatched_csrf_values():
    response = client.post(
        "/api/v1/auth/login",
        json={},
        cookies={"jobseeker_csrf": "cookie-token"},
        headers={"X-CSRF-Token": "different-token"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF validation failed"


def test_anonymous_mutation_passes_csrf_boundary_with_matching_values():
    response = client.post(
        "/api/v1/auth/login",
        json={},
        cookies={"jobseeker_csrf": "matching-token"},
        headers={"X-CSRF-Token": "matching-token"},
    )
    # The empty login payload is rejected by FastAPI validation only after
    # the real ASGI CSRF middleware has accepted the request.
    assert response.status_code == 422


def test_mutation_rejects_untrusted_origin_even_with_valid_csrf_token():
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


def test_mutation_rejects_cross_site_fetch_metadata_even_with_valid_csrf_token():
    response = client.post(
        "/api/v1/auth/login",
        json={},
        cookies={"jobseeker_csrf": "matching-token"},
        headers={
            "X-CSRF-Token": "matching-token",
            "Sec-Fetch-Site": "cross-site",
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Cross-site state changes are not allowed"


def test_safe_get_does_not_require_csrf_token():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "JobSeeker Intelligence"
