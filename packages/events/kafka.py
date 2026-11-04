"""Async Kafka event publisher with bounded delivery and graceful local fallback."""
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from apps.api.app.core.config import get_settings

logger = logging.getLogger(__name__)
ALLOWED_TOPICS = {"job.raw", "job.enriched", "user.activity", "application.dispatched", "application.status_changed", "email.classified", "ats.action.approved"}

async def publish_event(topic: str, payload: dict[str, Any], *, key: str | None = None) -> bool:
    """Publish a versioned domain event; False means disabled or delivery failed."""
    if topic not in ALLOWED_TOPICS:
        raise ValueError(f"Unsupported JobSeeker event topic: {topic}")
    settings = get_settings()
    if not settings.kafka_enabled:
        return False
    event = {
        "event_id": str(uuid4()), "event_type": topic, "schema_version": 1,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "producer": settings.kafka_client_id, "data": payload,
    }
    try:
        from aiokafka import AIOKafkaProducer
        producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            client_id=settings.kafka_client_id,
            value_serializer=lambda value: json.dumps(value, separators=(",", ":")).encode("utf-8"),
            key_serializer=lambda value: value.encode("utf-8") if value else None,
            request_timeout_ms=5000,
        )
        await producer.start()
        try:
            await producer.send_and_wait(topic, event, key=key)
        finally:
            await producer.stop()
        return True
    except Exception:
        logger.exception("Domain event delivery failed", extra={"topic": topic})
        return False
