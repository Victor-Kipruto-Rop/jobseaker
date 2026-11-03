"""Regression tests proving application endpoints enforce per-user ownership."""
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from packages.database.models import Base
from packages.database.models.identity import User
from packages.database.models.career import Application, ApplicationEvent
from apps.api.app.api.v1.applications import routes


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def two_users_and_applications(db):
    owner = User(email="owner@example.test", password_hash="unused")
    other = User(email="other@example.test", password_hash="unused")
    db.add_all([owner, other])
    db.flush()
    owned = Application(user_id=owner.id, role_title="Data Engineer", company_name="Acme")
    private = Application(user_id=other.id, role_title="Platform Engineer", company_name="Other Co")
    db.add_all([owned, private])
    db.flush()
    db.add(ApplicationEvent(
        user_id=other.id,
        application_id=private.id,
        event_type="application.created",
        details={"status": "draft"},
    ))
    db.commit()
    return owner, other, owned, private


def test_application_list_is_scoped_to_authenticated_user(db, two_users_and_applications):
    owner, other, owned, private = two_users_and_applications

    result = routes.list_applications(user=owner, db=db)

    assert [item["id"] for item in result] == [owned.id]
    assert private.id not in {item["id"] for item in result}


def test_user_cannot_update_another_users_application(db, two_users_and_applications):
    owner, other, owned, private = two_users_and_applications

    with pytest.raises(HTTPException) as exc:
        routes.update_application(
            application_id=private.id,
            body=routes.ApplicationUpdate(notes="unauthorized edit"),
            user=owner,
            db=db,
        )

    assert exc.value.status_code == 404
    db.refresh(private)
    assert private.notes == ""


def test_user_cannot_read_another_users_application_events(db, two_users_and_applications):
    owner, other, owned, private = two_users_and_applications

    with pytest.raises(HTTPException) as exc:
        routes.application_events(application_id=private.id, user=owner, db=db)

    assert exc.value.status_code == 404


def test_user_can_read_own_application_events(db, two_users_and_applications):
    owner, other, owned, private = two_users_and_applications
    db.add(ApplicationEvent(
        user_id=owner.id,
        application_id=owned.id,
        event_type="application.created",
        details={"status": "draft"},
    ))
    db.commit()

    events = routes.application_events(application_id=owned.id, user=owner, db=db)

    assert len(events) == 1
    assert events[0]["event_type"] == "application.created"
