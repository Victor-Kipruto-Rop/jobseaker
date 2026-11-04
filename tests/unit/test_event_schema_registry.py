from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from packages.events.contracts import EventEnvelope
from packages.events.schema_registry import (
    assert_backward_compatible, load_envelope_schema, validate_schema_registration,
)


def test_registered_envelope_schema_accepts_valid_domain_event():
    event = {
        "event_id": str(uuid4()),
        "event_type": "user.activity",
        "schema_version": 1,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "producer": "schema-test",
        "data": {"user_id": 42, "event_type": "save"},
    }
    assert EventEnvelope.model_validate(event).event_type == "user.activity"


def test_registered_envelope_schema_rejects_unknown_version():
    event = {
        "event_id": str(uuid4()), "event_type": "user.activity",
        "schema_version": 99, "occurred_at": datetime.now(timezone.utc).isoformat(),
        "producer": "schema-test", "data": {},
    }
    with pytest.raises(Exception):
        EventEnvelope.model_validate(event)


def test_schema_compatibility_allows_optional_additive_property():
    previous = {
        "type": "object", "required": ["event_id"],
        "properties": {"event_id": {"type": "string"}},
    }
    candidate = deepcopy(previous)
    candidate["properties"]["trace_id"] = {"type": "string"}
    validate_schema_registration(previous, candidate)


def test_schema_compatibility_rejects_new_required_property():
    previous = {
        "type": "object", "required": ["event_id"],
        "properties": {"event_id": {"type": "string"}},
    }
    candidate = deepcopy(previous)
    candidate["required"].append("tenant_id")
    candidate["properties"]["tenant_id"] = {"type": "string"}
    with pytest.raises(ValueError, match="required fields"):
        assert_backward_compatible(previous, candidate)


def test_schema_compatibility_rejects_property_removal():
    previous = {
        "type": "object", "properties": {
            "event_id": {"type": "string"}, "producer": {"type": "string"},
        },
    }
    candidate = {"type": "object", "properties": {"event_id": {"type": "string"}}}
    with pytest.raises(ValueError, match="property removal"):
        assert_backward_compatible(previous, candidate)
