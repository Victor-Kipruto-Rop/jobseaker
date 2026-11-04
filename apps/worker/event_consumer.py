"""Consumer process for candidate activity and Gmail intelligence events."""
from __future__ import annotations
import asyncio
import logging

from apps.api.app.core.config import get_settings
from packages.database.sessions import SessionLocal
from packages.events.consumer import run_kafka_consumer
from packages.events.handlers import handle_email_classified, handle_user_activity


async def main() -> None:
    settings = get_settings()
    if not settings.kafka_enabled:
        raise RuntimeError("KAFKA_ENABLED must be true for event consumers")
    logging.basicConfig(level="INFO")
    await run_kafka_consumer(
        SessionLocal,
        settings.kafka_bootstrap_servers,
        settings.kafka_consumer_group_id,
        ["user.activity", "email.classified"],
        {
            "user.activity": handle_user_activity,
            "email.classified": handle_email_classified,
        },
    )


if __name__ == "__main__":
    asyncio.run(main())
