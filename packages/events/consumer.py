"""Sequential Kafka consumer with inbox deduplication, bounded retries and DLQ."""
from __future__ import annotations
import asyncio
import json
import logging
from typing import Callable

from packages.events.contracts import EventEnvelope
from packages.events.inbox import consume_once
from packages.ops.metrics import EVENT_DELIVERY, CONSUMER_RETRIES, CONSUMER_DLQ

logger = logging.getLogger(__name__)


async def run_kafka_consumer(
    session_factory: Callable,
    bootstrap_servers: str,
    group_id: str,
    topics: list[str],
    handlers: dict[str, Callable],
    *,
    max_attempts: int = 5,
) -> None:
    from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

    consumer = AIOKafkaConsumer(
        *topics, bootstrap_servers=bootstrap_servers, group_id=group_id,
        enable_auto_commit=False, auto_offset_reset="earliest",
        value_deserializer=lambda raw: json.loads(raw.decode("utf-8")),
    )
    producer = AIOKafkaProducer(
        bootstrap_servers=bootstrap_servers,
        client_id=f"{group_id}-dlq",
        enable_idempotence=True,
        acks="all",
        value_serializer=lambda value: json.dumps(value, separators=(",", ":")).encode("utf-8"),
    )
    await producer.start()
    await consumer.start()
    try:
        async for message in consumer:
            envelope = message.value
            handler = handlers.get(message.topic)
            failure = None
            for attempt in range(max_attempts):
                try:
                    validated = EventEnvelope.model_validate(envelope)
                    if handler is None:
                        raise ValueError(f"No handler registered for topic {message.topic}")
                    with session_factory() as db:
                        consume_once(
                            db, f"{group_id}:{message.topic}", validated.model_dump(mode="json"),
                            handler,
                        )
                    await consumer.commit()
                    EVENT_DELIVERY.labels("consumer", message.topic, "processed").inc()
                    failure = None
                    break
                except Exception as exc:
                    failure = exc
                    CONSUMER_RETRIES.labels(message.topic).inc()
                    logger.exception(
                        "Kafka event processing failed",
                        extra={"topic": message.topic, "offset": message.offset,
                               "attempt": attempt + 1},
                    )
                    if attempt + 1 < max_attempts:
                        await asyncio.sleep(min(30.0, 2 ** attempt))
            if failure is not None:
                await producer.send_and_wait(
                    f"{message.topic}.dlq",
                    {"original_topic": message.topic, "partition": message.partition,
                     "offset": message.offset, "key": message.key.decode("utf-8") if message.key else None,
                     "event": envelope, "error": str(failure)[:2000],
                     "attempts": max_attempts},
                    key=message.key,
                )
                CONSUMER_DLQ.labels(message.topic).inc()
                EVENT_DELIVERY.labels("consumer", message.topic, "dead_letter").inc()
                await consumer.commit()
    finally:
        await consumer.stop()
        await producer.stop()
