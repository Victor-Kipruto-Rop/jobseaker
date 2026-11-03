import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from packages.database.models import Base
from packages.database.models.identity import User
from apps.api.app.core.security import create_session, resolve_session
from apps.api.app.api.v1.auth import routes


DATABASE_URL = os.getenv("JOBSEEKER_TEST_DATABASE_URL")


@pytest.fixture
def postgres_db():
    if not DATABASE_URL:
        pytest.skip("Set JOBSEEKER_TEST_DATABASE_URL to run PostgreSQL security integration tests")

    admin_engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    if admin_engine.dialect.name != "postgresql":
        admin_engine.dispose()
        pytest.skip("JOBSEEKER_TEST_DATABASE_URL must point to PostgreSQL")

    schema = "jobseeker_test_" + uuid4().hex
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    test_engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    Base.metadata.create_all(test_engine)
    try:
        with Session(test_engine) as session:
            yield session
    finally:
        test_engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()


def test_postgres_session_creation_and_revocation(postgres_db):
    user = User(email="pg-session@example.com", password_hash="unused")
    postgres_db.add(user)
    postgres_db.commit()

    raw_session, csrf_token, expires_at = create_session(postgres_db, user)
    resolved = resolve_session(postgres_db, raw_session)
    assert resolved is not None
    assert resolved[0].id == user.id
    assert csrf_token
    assert expires_at is not None

    routes.revoke_session(postgres_db, resolved[1])
    assert resolve_session(postgres_db, raw_session) is None


def test_postgres_password_recovery_hashes_token_and_revokes_sessions(postgres_db):
    user = User(email="pg-recovery@example.com", password_hash="old-password-hash")
    postgres_db.add(user)
    postgres_db.commit()
    raw_session, _, _ = create_session(postgres_db, user)

    raw_token = routes._new_account_token(
        postgres_db, user, "password_reset", routes.timedelta(minutes=30)
    )
    stored = postgres_db.query(routes.AccountToken).filter_by(user_id=user.id).one()
    assert stored.token_hash != raw_token

    result = routes.confirm_password_reset(
        routes.PasswordResetConfirm(token=raw_token, new_password="a-new-strong-password"),
        postgres_db,
    )
    assert result == {"status": "password_reset", "sessions_revoked": True}
    assert resolve_session(postgres_db, raw_session) is None

    with pytest.raises(routes.HTTPException):
        routes._consume_account_token(postgres_db, raw_token, "password_reset")


def test_postgres_expired_recovery_token_is_rejected(postgres_db):
    user = User(email="pg-expired@example.com", password_hash="unused")
    postgres_db.add(user)
    postgres_db.commit()
    raw_token = routes._new_account_token(
        postgres_db, user, "password_reset", routes.timedelta(seconds=-1)
    )
    with pytest.raises(routes.HTTPException) as error:
        routes._consume_account_token(postgres_db, raw_token, "password_reset")
    assert error.value.status_code == 400
