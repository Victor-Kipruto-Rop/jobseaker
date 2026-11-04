from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from apps.api.app.api.v1.integrations.calendar_routes import _calendar_event


def test_calendar_event_uses_explicit_timezone_and_duration():
    start = datetime(2026, 11, 12, 10, 30, tzinfo=timezone(timedelta(hours=3)))
    interview = SimpleNamespace(
        scheduled_at=start, duration_minutes=45, notes="Technical interview",
    )
    application = SimpleNamespace(role_title="Data Engineer", company_name="Acme")
    event = _calendar_event(interview, application)
    assert event["summary"] == "Data Engineer interview · Acme"
    assert event["start"]["dateTime"].endswith("+03:00")
    assert event["end"]["dateTime"].endswith("+03:00")
    assert datetime.fromisoformat(event["end"]["dateTime"]) - datetime.fromisoformat(
        event["start"]["dateTime"]
    ) == timedelta(minutes=45)


def test_calendar_event_refuses_ambiguous_timezone():
    interview = SimpleNamespace(
        scheduled_at=datetime(2026, 11, 12, 10, 30),
        duration_minutes=30, notes="",
    )
    with pytest.raises(HTTPException) as error:
        _calendar_event(interview, None)
    assert error.value.status_code == 422
