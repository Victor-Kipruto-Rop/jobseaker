import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from packages.database.models import Base
from packages.database.models.identity import User
from packages.database.models.entities import Approval
from packages.database.models.career import AuditLog, Application, ApplicationEvent
from packages.automation.approvals.service import create_approval, decide_approval, list_approvals

def _database():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return engine

def test_approval_is_user_scoped_audited_and_one_time():
    engine = _database()
    with Session(engine) as db:
        owner = User(email="owner@example.com", password_hash="x")
        other = User(email="other@example.com", password_hash="x")
        db.add_all([owner, other])
        db.commit()
        created = create_approval(db, owner.id, "email_send", {"draft_id": 7}, "Review before sending")
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

def test_application_submission_requires_and_applies_explicit_approval():
    engine = _database()
    with Session(engine) as db:
        owner = User(email="candidate@example.com", password_hash="x")
        db.add(owner)
        db.commit()
        application = Application(user_id=owner.id, role_title="Data Engineer", status="ready")
        db.add(application)
        db.commit()
        created = create_approval(db, owner.id, "application_submission",
                                  {"application_id": application.id}, "Candidate reviewed the final application")
        decide_approval(db, owner.id, created["id"], "approved", "Approved by candidate")
        db.refresh(application)
        assert application.status == "approved"
        events = db.scalars(select(ApplicationEvent).where(
            ApplicationEvent.application_id == application.id)).all()
        assert any(event.event_type == "application.submission_approval_granted" for event in events)
    Base.metadata.drop_all(engine)

def test_submission_approval_cannot_target_another_users_application():
    engine = _database()
    with Session(engine) as db:
        owner = User(email="owner2@example.com", password_hash="x")
        other = User(email="other2@example.com", password_hash="x")
        db.add_all([owner, other])
        db.commit()
        application = Application(user_id=other.id, role_title="Data Engineer", status="ready")
        db.add(application)
        db.commit()
        created = create_approval(db, owner.id, "application_submission",
                                  {"application_id": application.id}, "Attempted cross-account approval")
        with pytest.raises(ValueError):
            decide_approval(db, owner.id, created["id"], "approved")
    Base.metadata.drop_all(engine)
