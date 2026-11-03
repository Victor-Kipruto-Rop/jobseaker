import hashlib
import hmac
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from apps.api.app.core.config import get_settings
from apps.api.app.core.security import resolve_session
from apps.api.app.lifespan import lifespan
from apps.api.app.api.v1.router import router
from apps.api.app.health.routes import router as health_router
from packages.database.sessions import SessionLocal

s = get_settings()
app = FastAPI(title="JobSeeker Intelligence", version="0.3.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=s.allowed_origins, allow_credentials=True,
                   allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                   allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-CSRF-Token"])

@app.middleware("http")
async def csrf_protection(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
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
    return await call_next(request)

app.include_router(health_router)
app.include_router(router, prefix="/api/v1")

@app.get("/")
def root():
    return {"name": "JobSeeker Intelligence", "version": "0.3.0", "docs": "/docs"}
