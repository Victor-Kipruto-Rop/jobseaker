from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from packages.database.models import Base
from packages.database.models.identity import User
from packages.database.models.career import UserAIBudget, Notification
from packages.ai.budget import record_ai_usage

def test_ai_budget_alert_is_emitted_once_per_month():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(email="budget@example.com", password_hash="x")
        db.add(user)
        db.flush()
        db.add(UserAIBudget(user_id=user.id, monthly_token_limit=100,
                            hard_token_limit_enabled=False, alert_threshold_percent=80))
        db.commit()
        record_ai_usage(db, user.id, "mock", "mock-v1", 40, 40)
        db.commit()
        record_ai_usage(db, user.id, "mock", "mock-v1", 10, 10)
        db.commit()
        alerts = db.scalars(select(Notification).where(
            Notification.user_id == user.id,
            Notification.title == "AI token budget threshold reached")).all()
        assert len(alerts) == 1
        assert "ai-budget:" in alerts[0].body
    Base.metadata.drop_all(engine)
