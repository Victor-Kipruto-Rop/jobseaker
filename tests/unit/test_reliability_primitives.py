from datetime import datetime, timezone
import base64

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from packages.database.models import Base
from packages.database.models.career import EventInbox, EventOutbox, Application, ApplicationDispatchKey
from packages.database.models.identity import User
from packages.events.outbox import enqueue_event
from packages.events.inbox import consume_once
from packages.automation.idempotency import DispatchConflict, reserve_application_dispatch
from packages.recommendations.skill_graph import expand_skills, skill_match_score
from packages.ops.circuit_breaker import CircuitBreaker, CircuitOpen, CircuitState
from packages.security.credential_vault import encrypt_credential, decrypt_credential


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)


@pytest.fixture
def owner(db):
    user = User(email="reliability@example.com", password_hash="unused")
    db.add(user)
    db.flush()
    return user


def test_outbox_event_is_part_of_callers_transaction(db, owner):
    event_id = enqueue_event(
        db, "application.status_changed",
        {"user_id": owner.id, "application_id": 12, "to": "draft"},
        partition_key=str(owner.id),
    )
    row = db.scalar(select(EventOutbox).where(EventOutbox.event_id == event_id))
    assert row is not None
    assert row.status == "pending"
    assert row.envelope["event_id"] == event_id
    assert row.partition_key == str(owner.id)


def test_outbox_rejects_unknown_topic(db):
    with pytest.raises(ValueError):
        enqueue_event(db, "unknown.topic", {})


def test_inbox_deduplicates_per_consumer_and_event(db):
    calls = []
    def handler(session, envelope):
        calls.append(envelope["event_id"])
        return {"stored": True}

    envelope = {
        "event_id": "00000000-0000-4000-8000-000000000001",
        "event_type": "user.activity", "schema_version": 1,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "producer": "test", "data": {},
    }
    first = consume_once(db, "analytics-v1", envelope, handler)
    second = consume_once(db, "analytics-v1", envelope, handler)
    third = consume_once(db, "recommendations-v1", envelope, handler)
    assert first == (True, {"stored": True})
    assert second == (False, {"stored": True})
    assert third[0] is True
    assert len(calls) == 2
    assert db.scalar(select(EventInbox).where(EventInbox.consumer_name == "analytics-v1"))


def test_application_dispatch_is_idempotent_and_payload_bound(db, owner):
    app = Application(user_id=owner.id, role_title="Data Engineer")
    db.add(app)
    db.flush()
    payload = {"application_id": app.id, "approved": True}
    first = reserve_application_dispatch(
        db, user_id=owner.id, application_id=app.id,
        idempotency_key="dispatch-001", payload=payload,
    )
    again = reserve_application_dispatch(
        db, user_id=owner.id, application_id=app.id,
        idempotency_key="dispatch-001", payload=payload,
    )
    assert first.id == again.id
    with pytest.raises(DispatchConflict):
        reserve_application_dispatch(
            db, user_id=owner.id, application_id=app.id,
            idempotency_key="dispatch-002", payload=payload,
        )
    assert db.scalar(select(ApplicationDispatchKey).where(
        ApplicationDispatchKey.application_id == app.id
    ))


def test_skill_graph_maps_equivalent_data_platform_skills():
    expanded = expand_skills(["PostgreSQL"])
    assert expanded["sql"] == 1
    assert expanded["relational databases"] == 1
    score, evidence = skill_match_score(
        ["PostgreSQL", "Apache Kafka"], ["SQL", "event streaming", "Java"],
    )
    assert score > 0
    assert {item["required"] for item in evidence} == {"sql", "event streaming"}


def test_credential_vault_authenticates_and_binds_purpose(monkeypatch):
    key = base64.urlsafe_b64encode(b"x" * 32).decode()
    monkeypatch.setenv("JOBSEEKER_CREDENTIAL_KEK", key)
    encrypted = encrypt_credential("oauth-refresh-token", purpose="gmail")
    assert decrypt_credential(encrypted, purpose="gmail") == "oauth-refresh-token"
    with pytest.raises(Exception):
        decrypt_credential(encrypted, purpose="calendar")


def test_circuit_breaker_opens_and_recovers():
    breaker = CircuitBreaker(failure_threshold=2, recovery_seconds=0.01)
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN
    with pytest.raises(CircuitOpen):
        breaker.before_call()
    import time
    time.sleep(0.02)
    assert breaker.state == CircuitState.HALF_OPEN
    breaker.record_success()
    assert breaker.state == CircuitState.CLOSED
