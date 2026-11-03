import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from packages.database.models import Base
from packages.database.models.identity import User
from packages.database.models.career import CandidateOpportunity

def test_opportunity_source_url_is_unique_per_user_not_globally():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        first = User(email="first@example.com", password_hash="x")
        second = User(email="second@example.com", password_hash="x")
        db.add_all([first, second])
        db.flush()
        db.add(CandidateOpportunity(user_id=first.id, title="Data Engineer",
            source_url="https://jobs.example.com/role/1"))
        db.commit()
        db.add(CandidateOpportunity(user_id=second.id, title="Data Engineer",
            source_url="https://jobs.example.com/role/1"))
        db.commit()
        db.add(CandidateOpportunity(user_id=first.id, title="Duplicate",
            source_url="https://jobs.example.com/role/1"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    Base.metadata.drop_all(engine)

def test_multiple_manual_opportunities_can_have_empty_source_urls():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(email="manual@example.com", password_hash="x")
        db.add(user)
        db.flush()
        db.add_all([
            CandidateOpportunity(user_id=user.id, title="Role A", source_url=""),
            CandidateOpportunity(user_id=user.id, title="Role B", source_url=""),
        ])
        db.commit()
    Base.metadata.drop_all(engine)
