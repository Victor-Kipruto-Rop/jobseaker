"""Standalone durable Kafka outbox relay process."""
from __future__ import annotations

import asyncio
import json
import logging
import os

from aiokafka import AIOKafkaProducer
from apps.api.app.core.config import get_settings
from packages.database.sessions import SessionLocal
from packages.events.outbox import run_outbox_relay


async def main() -> None:
    settings = get_settings()
    if not settings.kafka_enabled:
        raise RuntimeError("KAFKA_ENABLED must be true for the outbox relay")
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    await run_outbox_relay(
        SessionLocal,
        lambda: AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            client_id=f"{settings.kafka_client_id}-outbox-relay",
            enable_idempotence=True,
            acks="all",
            value_serializer=lambda value: json.dumps(value, separators=(",", ":")).encode("utf-8"),
            request_timeout_ms=10000,
        ),
        poll_seconds=1.0,
    )


if __name__ == "__main__":
    asyncio.run(main())
