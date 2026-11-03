import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from packages.database.models import Base
from packages.database.models.identity import User
from packages.database.models.career import UserAIBudget
from packages.database.models.entities import AIUsageReservation
from packages.ai.budget import AIQuotaExceeded, finish_ai_reservation, reserve_ai_tokens, record_ai_usage

def _db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return engine

def test_reservations_prevent_concurrent_requests_exceeding_monthly_limit():
    engine = _db()
    with Session(engine) as db:
        user = User(email="reserve@example.com", password_hash="x")
        db.add(user)
        db.flush()
        db.add(UserAIBudget(user_id=user.id, monthly_token_limit=100,
                            hard_token_limit_enabled=True, alert_threshold_percent=80))
        db.commit()
        first = reserve_ai_tokens(db, user.id, 75)
        assert first is not None
        with pytest.raises(AIQuotaExceeded):
            reserve_ai_tokens(db, user.id, 30)
        finish_ai_reservation(db, user.id, first, "failed")
        db.commit()
        second = reserve_ai_tokens(db, user.id, 75)
        assert second is not None
    Base.metadata.drop_all(engine)

def test_completed_reservation_moves_into_actual_usage_accounting():
    engine = _db()
    with Session(engine) as db:
        user = User(email="complete@example.com", password_hash="x")
        db.add(user)
        db.flush()
        db.add(UserAIBudget(user_id=user.id, monthly_token_limit=100,
                            hard_token_limit_enabled=True, alert_threshold_percent=80))
        db.commit()
        reservation_id = reserve_ai_tokens(db, user.id, 60)
        record_ai_usage(db, user.id, "mock", "mock-v1", 20, 20)
        finish_ai_reservation(db, user.id, reservation_id, "completed")
        db.commit()
        with pytest.raises(AIQuotaExceeded):
            reserve_ai_tokens(db, user.id, 41)
        row = db.get(AIUsageReservation, reservation_id)
        assert row.status == "completed"
        assert row.completed_at is not None
    Base.metadata.drop_all(engine)

def test_expired_reservations_do_not_consume_monthly_capacity():
    engine = _db()
    with Session(engine) as db:
        user = User(email="expiry@example.com", password_hash="x")
        db.add(user)
        db.flush()
        db.add(UserAIBudget(user_id=user.id, monthly_token_limit=100,
                            hard_token_limit_enabled=True, alert_threshold_percent=80))
        db.flush()
        expired = AIUsageReservation(request_id="expired-reservation", user_id=user.id,
            reserved_tokens=100, status="reserved",
            created_at=datetime.now(timezone.utc)-timedelta(minutes=10),
            expires_at=datetime.now(timezone.utc)-timedelta(minutes=1))
        db.add(expired)
        db.commit()
        assert reserve_ai_tokens(db, user.id, 100) is not None
    Base.metadata.drop_all(engine)
