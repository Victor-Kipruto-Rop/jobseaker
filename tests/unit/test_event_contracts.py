from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from packages.events.contracts import EventEnvelope


def envelope(**overrides):
    value = {
        "event_id": str(uuid4()),
        "event_type": "user.activity",
        "schema_version": 1,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "producer": "contract-test",
        "data": {"user_id": 12, "event_type": "save"},
    }
    value.update(overrides)
    return value


def test_event_contract_accepts_supported_v1_payload():
    result = EventEnvelope.model_validate(envelope())
    assert result.schema_version == 1
    assert result.data["user_id"] == 12


def test_event_contract_rejects_unknown_schema_version():
    with pytest.raises(ValidationError):
        EventEnvelope.model_validate(envelope(schema_version=2))


def test_event_contract_rejects_invalid_event_uuid():
    with pytest.raises(ValidationError):
        EventEnvelope.model_validate(envelope(event_id="not-a-uuid"))


def test_event_contract_rejects_missing_user_scope():
    with pytest.raises(ValidationError):
        EventEnvelope.model_validate(envelope(data={"event_type": "save"}))


def test_email_event_requires_message_reference():
    with pytest.raises(ValidationError):
        EventEnvelope.model_validate(envelope(
            event_type="email.classified", data={"user_id": 12},
        ))
