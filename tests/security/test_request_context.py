from fastapi import Response
from starlette.requests import Request
from apps.api.app.main import request_context

def _request(request_id: str = ""):
    headers = [(b"x-request-id", request_id.encode())] if request_id else []
    return Request({
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "GET", "scheme": "http", "path": "/health",
        "raw_path": b"/health", "query_string": b"",
        "headers": headers, "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
    })

async def test_request_context_preserves_valid_correlation_id_and_adds_security_headers():
    request = _request("support-ticket-1234")
    async def next_response(_request):
        return Response(status_code=200)
    response = await request_context(request, next_response)
    assert response.headers["X-Request-ID"] == "support-ticket-1234"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Cache-Control"] == "no-store"

async def test_request_context_replaces_untrusted_request_id():
    request = _request("bad value\nforged-log-entry")
    async def next_response(_request):
        return Response(status_code=204)
    response = await request_context(request, next_response)
    assert response.headers["X-Request-ID"] != "bad value\nforged-log-entry"
    assert len(response.headers["X-Request-ID"]) == 32
