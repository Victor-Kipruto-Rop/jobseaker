"""Versioned, strict event envelope contract."""
from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator
from packages.events.kafka import ALLOWED_TOPICS


class EventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(min_length=36, max_length=36)
    event_type: str = Field(min_length=1, max_length=120)
    schema_version: int = Field(ge=1)
    occurred_at: datetime
    producer: str = Field(min_length=1, max_length=120)
    data: dict[str, Any]

    @field_validator("event_type")
    @classmethod
    def supported_event(cls, value: str) -> str:
        if value not in ALLOWED_TOPICS:
            raise ValueError("Unsupported event type")
        return value
