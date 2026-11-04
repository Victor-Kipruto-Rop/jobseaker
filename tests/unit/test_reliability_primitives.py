from datetime import datetime, timezone
import base64

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from packages.database.models import Base
from packages.database.models.career import EventInbox, EventOutbox, Application, ApplicationDispatchKey, CandidatePreferenceState, Notification
from packages.database.models.identity import User
from packages.events.outbox import enqueue_event, relay_outbox_batch
from packages.events.inbox import consume_once
from packages.events.handlers import handle_user_activity, handle_email_classified
from packages.automation.idempotency import DispatchConflict, reserve_application_dispatch
from packages.recommendations.skill_graph import expand_skills, skill_match_score
from packages.ops.circuit_breaker import CircuitBreaker, CircuitOpen, CircuitState
from packages.security.credential_vault import (\n    encrypt_credential, decrypt_credential, rewrap_credential, credential_key_id,\n)


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



def test_outbox_relay_publishes_stable_event_envelope(db, owner):
    enqueue_event(db, "user.activity", {"user_id": owner.id}, partition_key=str(owner.id))
    db.commit()
    factory = sessionmaker(bind=db.get_bind(), expire_on_commit=False)

    class Producer:
        def __init__(self):
            self.sent = []
        async def send_and_wait(self, topic, value, key=None):
            self.sent.append((topic, value, key))

    producer = Producer()
    import asyncio
    result = asyncio.run(relay_outbox_batch(factory, producer))
    assert result["published"] == 1
    assert producer.sent[0][0] == "user.activity"
    assert producer.sent[0][1]["event_id"]
    row = db.scalar(select(EventOutbox))
    assert row.status == "published"
    assert row.envelope["event_id"] == producer.sent[0][1]["event_id"]


def test_outbox_relay_schedules_exponential_retry(db, owner):
    enqueue_event(db, "user.activity", {"user_id": owner.id})
    db.commit()
    factory = sessionmaker(bind=db.get_bind(), expire_on_commit=False)

    class FailingProducer:
        async def send_and_wait(self, topic, value, key=None):
            raise RuntimeError("broker unavailable")

    import asyncio
    result = asyncio.run(relay_outbox_batch(factory, FailingProducer()))
    assert result["retrying"] == 1
    row = db.scalar(select(EventOutbox))
    assert row.status == "retry"
    assert row.attempts == 1
    assert "broker unavailable" in row.last_error


def test_dispatch_key_prevents_same_job_across_draft_records(db, owner):
    first = Application(user_id=owner.id, role_title="Data Engineer")
    second = Application(user_id=owner.id, role_title="Data Engineer")
    db.add_all([first, second])
    db.flush()
    reserve_application_dispatch(
        db, user_id=owner.id, application_id=first.id,
        idempotency_key="first", payload={"job_key": "https://jobs.example/role/1"},
    )
    with pytest.raises(DispatchConflict):
        reserve_application_dispatch(
            db, user_id=owner.id, application_id=second.id,
            idempotency_key="second", payload={"job_key": "https://jobs.example/role/1"},
        )



def test_async_circuit_breaker_tracks_provider_failures():
    import asyncio
    breaker = CircuitBreaker(failure_threshold=1, recovery_seconds=0.01)
    async def failing():
        raise RuntimeError("upstream down")
    with pytest.raises(RuntimeError):
        asyncio.run(breaker.call_async(failing))
    assert breaker.state == CircuitState.OPEN
    with pytest.raises(CircuitOpen):
        asyncio.run(breaker.call_async(failing))



def test_user_activity_consumer_updates_preference_vector_once(db, owner):
    envelope = {
        "event_id": "00000000-0000-4000-8000-000000000002",
        "event_type": "user.activity", "schema_version": 1,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "producer": "test", "data": {
            "user_id": owner.id, "event_type": "save",
            "feature_snapshot": {"skill_overlap": 0.9, "remote_match": 1.0},
        },
    }
    first = consume_once(db, "career-intelligence:user.activity", envelope, handle_user_activity)
    second = consume_once(db, "career-intelligence:user.activity", envelope, handle_user_activity)
    state = db.scalar(select(CandidatePreferenceState).where(
        CandidatePreferenceState.user_id == owner.id
    ))
    assert first[0] is True and second[0] is False
    assert state.preference_vector["skill_overlap"] > 0
    assert state.interaction_count == 1


def test_email_consumer_creates_review_notification(db, owner):
    envelope = {
        "event_id": "00000000-0000-4000-8000-000000000003",
        "event_type": "email.classified", "schema_version": 1,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "producer": "test", "data": {
            "user_id": owner.id, "email_message_id": 77,
            "classification": "interview_invitation", "action_required": True,
        },
    }
    consume_once(db, "career-intelligence:email.classified", envelope, handle_email_classified)
    notices = db.scalars(select(Notification).where(Notification.user_id == owner.id)).all()
    assert len(notices) == 1
    assert "needs review" in notices[0].title.lower()


def test_credential_key_rotation_rewraps_without_changing_plaintext(monkeypatch):
    old_key = base64.urlsafe_b64encode(b"o" * 32).decode()
    new_key = base64.urlsafe_b64encode(b"n" * 32).decode()
    monkeypatch.setenv("JOBSEEKER_CREDENTIAL_KEYRING", __import__("json").dumps({
        "key-2026-10": old_key, "key-2026-11": new_key,
    }))
    monkeypatch.setenv("JOBSEEKER_CREDENTIAL_ACTIVE_KEY_ID", "key-2026-10")
    monkeypatch.delenv("JOBSEEKER_CREDENTIAL_KEK", raising=False)
    original = encrypt_credential("refresh-token-value", purpose="gmail")
    assert credential_key_id(original) == "key-2026-10"
    monkeypatch.setenv("JOBSEEKER_CREDENTIAL_ACTIVE_KEY_ID", "key-2026-11")
    rotated = rewrap_credential(original, purpose="gmail")
    assert credential_key_id(rotated) == "key-2026-11"
    assert decrypt_credential(rotated, purpose="gmail") == "refresh-token-value"
    assert decrypt_credential(original, purpose="gmail") == "refresh-token-value"


def test_credential_keyring_rejects_unknown_key_id(monkeypatch):
    key = base64.urlsafe_b64encode(b"z" * 32).decode()
    monkeypatch.setenv("JOBSEEKER_CREDENTIAL_KEYRING", __import__("json").dumps({"known": key}))
    monkeypatch.setenv("JOBSEEKER_CREDENTIAL_ACTIVE_KEY_ID", "missing")
    with pytest.raises(RuntimeError):
        encrypt_credential("secret", purpose="gmail")
