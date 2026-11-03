from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from packages.database.models import Base
from packages.database.models.identity import User
from apps.api.app.core.security import create_session, resolve_session, revoke_session

def test_session_token_is_resolvable_then_revocable():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(email="session-test@example.com", password_hash="not-used")
        db.add(user)
        db.commit()
        token, csrf_token, expires_at = create_session(db, user)
        resolved = resolve_session(db, token)
        assert resolved is not None
        assert resolved[0].id == user.id
        assert resolved[1].csrf_hash
        assert csrf_token and expires_at is not None
        revoke_session(db, resolved[1])
        assert resolve_session(db, token) is None
    Base.metadata.drop_all(engine)


def test_expired_session_is_rejected():
    from datetime import datetime, timedelta, timezone

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(email="session-expired@example.com", password_hash="not-used")
        db.add(user)
        db.commit()
        token, _, _ = create_session(db, user)
        resolved = resolve_session(db, token)
        assert resolved is not None
        resolved[1].expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
        assert resolve_session(db, token) is None
    Base.metadata.drop_all(engine)


def test_inactive_user_session_is_rejected():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(email="session-inactive@example.com", password_hash="not-used")
        db.add(user)
        db.commit()
        token, _, _ = create_session(db, user)
        user.is_active = False
        db.commit()
        assert resolve_session(db, token) is None
    Base.metadata.drop_all(engine)
