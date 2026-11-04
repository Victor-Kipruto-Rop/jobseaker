import pytest
from packages.events.schema_registry import load_envelope_schema, assert_backward_compatible, validate_envelope

def test_v2_schema_adds_optional_correlation_fields():
    v1 = load_envelope_schema(1)
    v2 = load_envelope_schema(2)
    assert "correlation_id" not in v1["properties"]
    assert "correlation_id" in v2["properties"]

def test_v2_event_accepts_correlation_and_causation():
    validate_envelope({
        "event_id": "123e4567-e89b-12d3-a456-426614174000",
        "event_type": "ats.action.approved", "schema_version": 2,
        "occurred_at": "2026-11-04T12:00:00Z", "producer": "test",
        "data": {"user_id": 7, "application_id": 3, "field_id": "email"},
        "correlation_id": "application:3",
    })

def test_backward_compatibility_rejects_removed_optional_property():
    with pytest.raises(ValueError):
        assert_backward_compatible(
            {"type": "object", "properties": {"name": {"type": "string"}}, "required": []},
            {"type": "object", "properties": {}, "required": []},
        )
