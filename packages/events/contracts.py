"""Versioned, strict event envelope and topic payload contracts."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.events.kafka import ALLOWED_TOPICS


class EventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(min_length=36, max_length=36)
    event_type: str = Field(min_length=1, max_length=120)
    schema_version: Literal[1, 2] = 1
    occurred_at: datetime
    producer: str = Field(min_length=1, max_length=120)
    data: dict[str, Any]
    trace_context: dict[str, str] = Field(default_factory=dict)
    correlation_id: str | None = Field(default=None, max_length=120)
    causation_id: str | None = Field(default=None, max_length=120)

    @field_validator("event_id")
    @classmethod
    def valid_event_id(cls, value: str) -> str:
        try:
            UUID(value)
        except ValueError as exc:
            raise ValueError("event_id must be a UUID") from exc
        return value

    @model_validator(mode="after")
    def validate_registered_schema(self):
        from packages.events.schema_registry import validate_envelope
        validate_envelope(self.model_dump(mode="json", exclude_none=True))
        return self

    @field_validator("event_type")
    @classmethod
    def supported_event(cls, value: str) -> str:
        if value not in ALLOWED_TOPICS:
            raise ValueError("Unsupported event type")
        return value

    @field_validator("data")
    @classmethod
    def validate_topic_payload(cls, value: dict[str, Any], info):
        topic = info.data.get("event_type")
        if topic in {"user.activity", "email.classified", "application.status_changed",
                     "application.dispatched", "ats.action.approved"}:
            user_id = value.get("user_id")
            if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
                raise ValueError(f"{topic} requires a positive integer user_id")
        if topic in {"application.status_changed", "application.dispatched"}:
            app_id = value.get("application_id")
            if isinstance(app_id, bool) or not isinstance(app_id, int) or app_id <= 0:
                raise ValueError(f"{topic} requires a positive integer application_id")
        if topic == "ats.action.approved":
            if not isinstance(value.get("field_id"), str) or not value.get("field_id"):
                raise ValueError("ats.action.approved requires field_id")
        if topic == "email.classified":
            email_id = value.get("email_message_id")
            if isinstance(email_id, bool) or not isinstance(email_id, int) or email_id <= 0:
                raise ValueError("email.classified requires a positive integer email_message_id")
        return value
