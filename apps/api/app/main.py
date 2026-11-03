import hashlib
import hmac
import re
import time
from uuid import uuid4
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from apps.api.app.core.config import get_settings
from apps.api.app.core.security import resolve_session
from apps.api.app.core.origin import is_allowed_origin, origin_from_referer
from apps.api.app.lifespan import lifespan
from apps.api.app.api.v1.router import router
from apps.api.app.health.routes import router as health_router
from packages.database.sessions import SessionLocal
import structlog

s = get_settings()
app = FastAPI(title="JobSeeker Intelligence", version="0.3.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=s.allowed_origins, allow_credentials=True,
                   allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                   allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-CSRF-Token"],
                   expose_headers=["X-Request-ID"])

@app.middleware("http")
async def csrf_protection(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        referer = request.headers.get("referer")
        browser_origin = origin or origin_from_referer(referer)
        if browser_origin and not is_allowed_origin(browser_origin, s.allowed_origins):
            return JSONResponse(status_code=403, content={"detail": "Untrusted request origin"})
        fetch_site = request.headers.get("sec-fetch-site", "").lower()
        if fetch_site == "cross-site":
            return JSONResponse(status_code=403, content={"detail": "Cross-site state changes are not allowed"})
        session_token = request.cookies.get("jobseeker_session")
        csrf_cookie = request.cookies.get("jobseeker_csrf")
        csrf_header = request.headers.get("x-csrf-token")
        if session_token:
            with SessionLocal() as db:
                resolved = resolve_session(db, session_token)
                if resolved:
                    if not csrf_cookie or not csrf_header or not hmac.compare_digest(csrf_cookie, csrf_header):
                        return JSONResponse(status_code=403, content={"detail": "CSRF validation failed"})
                    expected = hashlib.sha256(csrf_cookie.encode("utf-8")).hexdigest()
                    if not hmac.compare_digest(resolved[1].csrf_hash, expected):
                        return JSONResponse(status_code=403, content={"detail": "CSRF session binding failed"})
                else:
                    public_token_routes = {
                        "/api/v1/auth/login", "/api/v1/auth/register",
                        "/api/v1/auth/password-reset/request",
                        "/api/v1/auth/password-reset/confirm",
                        "/api/v1/auth/verification/confirm",
                    }
                    if request.url.path not in public_token_routes:
                        return JSONResponse(status_code=403, content={"detail": "Session is invalid"})
                    if not csrf_cookie or not csrf_header or not hmac.compare_digest(csrf_cookie, csrf_header):
                        return JSONResponse(status_code=403, content={"detail": "CSRF validation failed"})
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Cache-Control", "no-store")
    if s.app_env == "production":
        response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
    return response

app.include_router(health_router)
app.include_router(router, prefix="/api/v1")

@app.get("/")
def root():
    return {"name": "JobSeeker Intelligence", "version": "0.3.0", "docs": "/docs"}

_request_logger = structlog.get_logger("jobseeker.http")

@app.middleware("http")
async def request_context(request: Request, call_next):
    supplied = request.headers.get("x-request-id", "")
    request_id = supplied if re.fullmatch(r"[A-Za-z0-9._-]{8,80}", supplied) else uuid4().hex
    request.state.request_id = request_id
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        _request_logger.exception("http.request.failed", request_id=request_id,
                                  method=request.method, path=request.url.path)
        raise
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    _request_logger.info("http.request.completed", request_id=request_id,
                         method=request.method, path=request.url.path,
                         status_code=response.status_code, duration_ms=duration_ms)
    return response
