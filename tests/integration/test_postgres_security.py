import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from packages.database.models.identity import User
from apps.api.app.core.security import create_session, resolve_session
from apps.api.app.api.v1.auth import routes


DATABASE_URL = os.getenv("JOBSEEKER_TEST_DATABASE_URL")
ROOT = Path(__file__).resolve().parents[2]


def _alembic_config(connection):
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["connection"] = connection
    return config


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
    connection = test_engine.connect()
    try:
        command.upgrade(_alembic_config(connection), "head")
        with Session(bind=connection) as session:
            yield session
    finally:
        connection.close()
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
    assert resolved[1].token_hash != raw_session
    import hashlib
    assert resolved[1].csrf_hash == hashlib.sha256(csrf_token.encode("utf-8")).hexdigest()
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


def test_postgres_migration_upgrade_and_downgrade_are_repeatable(postgres_db):
    postgres_db.commit()
    connection = postgres_db.connection()
    config = _alembic_config(connection)
    command.downgrade(config, "20261103_0007")
    postgres_db.commit()
    columns = {column["name"] for column in inspect(connection).get_columns("users")}
    assert "role" not in columns

    command.upgrade(config, "head")
    postgres_db.commit()
    columns = {column["name"] for column in inspect(connection).get_columns("users")}
    assert "role" in columns



def test_postgres_expired_and_inactive_sessions_are_rejected(postgres_db):
    user = User(email="pg-expiry@example.com", password_hash="unused")
    postgres_db.add(user)
    postgres_db.commit()
    raw_session, _, _ = create_session(postgres_db, user)
    resolved = resolve_session(postgres_db, raw_session)
    assert resolved is not None

    resolved[1].expires_at = routes.datetime.now(routes.timezone.utc) - routes.timedelta(seconds=1)
    postgres_db.commit()
    assert resolve_session(postgres_db, raw_session) is None

    raw_session, _, _ = create_session(postgres_db, user)
    user.is_active = False
    postgres_db.commit()
    assert resolve_session(postgres_db, raw_session) is None


def test_postgres_email_verification_token_is_hashed_and_single_use(postgres_db):
    user = User(email="pg-verification@example.com", password_hash="unused")
    postgres_db.add(user)
    postgres_db.commit()
    raw_token = routes._new_account_token(
        postgres_db, user, "email_verification", routes.timedelta(hours=24)
    )
    stored = postgres_db.query(routes.AccountToken).filter_by(
        user_id=user.id, purpose="email_verification"
    ).one()
    assert stored.token_hash != raw_token

    result = routes.confirm_verification(routes.TokenConfirm(token=raw_token), postgres_db)
    assert result == {"status": "verified"}
    assert user.is_verified is True
    with pytest.raises(routes.HTTPException):
        routes._consume_account_token(postgres_db, raw_token, "email_verification")



def test_postgres_recovery_token_is_bound_to_its_owner(postgres_db):
    owner = User(email="pg-token-owner@example.com", password_hash="owner-old-hash")
    other = User(email="pg-token-other@example.com", password_hash="other-old-hash")
    postgres_db.add_all([owner, other])
    postgres_db.commit()

    token = routes._new_account_token(
        postgres_db, owner, "password_reset", routes.timedelta(minutes=30)
    )
    result = routes.confirm_password_reset(
        routes.PasswordResetConfirm(token=token, new_password="owner-new-password-123"),
        postgres_db,
    )
    postgres_db.refresh(owner)
    postgres_db.refresh(other)

    assert result["status"] == "password_reset"
    assert owner.password_hash != "owner-old-hash"
    assert other.password_hash == "other-old-hash"
