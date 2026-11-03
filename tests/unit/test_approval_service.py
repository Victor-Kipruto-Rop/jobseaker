import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from packages.database.models import Base
from packages.database.models.identity import User
from packages.database.models.entities import Approval
from packages.database.models.career import AuditLog
from packages.automation.approvals.service import create_approval, decide_approval, list_approvals

def test_approval_is_user_scoped_audited_and_one_time():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        owner = User(email="owner@example.com", password_hash="x")
        other = User(email="other@example.com", password_hash="x")
        db.add_all([owner, other])
        db.commit()
        created = create_approval(db, owner.id, "application_submission", {"application_id": 7}, "Review before submission")
        assert list_approvals(db, owner.id)[0]["status"] == "pending"
        assert list_approvals(db, other.id) == []
        decision = decide_approval(db, owner.id, created["id"], "approved", "Reviewed manually")
        assert decision["status"] == "approved"
        with pytest.raises(ValueError):
            decide_approval(db, owner.id, created["id"], "rejected")
        assert db.scalar(select(Approval).where(Approval.id == created["id"])).status == "approved"
        actions = db.scalars(select(AuditLog.action).where(AuditLog.user_id == owner.id)).all()
        assert "approval.requested" in actions and "approval.approved" in actions
    Base.metadata.drop_all(engine)
