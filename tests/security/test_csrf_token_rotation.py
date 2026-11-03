import hashlib
from types import SimpleNamespace
from fastapi import Response
from starlette.requests import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from packages.database.models import Base
from packages.database.models.identity import User
from apps.api.app.core.security import create_session
from apps.api.app.api.v1.auth import routes

def _request(cookie: str | None = None):
    headers = []
    if cookie:
        headers.append((b"cookie", cookie.encode("ascii")))
    return Request({
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "GET", "scheme": "http", "path": "/api/v1/auth/csrf",
        "raw_path": b"/api/v1/auth/csrf", "query_string": b"",
        "headers": headers, "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
    })

def test_csrf_endpoint_rotates_and_binds_token_to_authenticated_session(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(routes, "get_settings", lambda: SimpleNamespace(app_env="local"))
    with Session(engine) as db:
        user = User(email="csrf-test@example.com", password_hash="unused")
        db.add(user)
        db.commit()
        session_token, original_csrf, _ = create_session(db, user)
        original_hash = hashlib.sha256(original_csrf.encode()).hexdigest()
        response = Response()
        result = routes.csrf(_request(f"jobseeker_session={session_token}"), response, db)
        session = db.query(routes.UserSession).filter_by(user_id=user.id).one()
        assert result["authenticated"] is True
        assert result["csrf_token"] != original_csrf
        assert session.csrf_hash == hashlib.sha256(result["csrf_token"].encode()).hexdigest()
        assert session.csrf_hash != original_hash
        assert result["csrf_token"] in response.headers["set-cookie"]
    Base.metadata.drop_all(engine)

def test_csrf_endpoint_issues_anonymous_bootstrap_token(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(routes, "get_settings", lambda: SimpleNamespace(app_env="local"))
    with Session(engine) as db:
        response = Response()
        result = routes.csrf(_request(), response, db)
        assert result["authenticated"] is False
        assert len(result["csrf_token"]) >= 32
        assert "jobseeker_csrf=" in response.headers["set-cookie"]
    Base.metadata.drop_all(engine)
