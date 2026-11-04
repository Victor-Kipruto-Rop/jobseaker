"""JobSeeker worker entry point with a durable assistant outbox dispatcher."""
from __future__ import annotations
import logging
import os
import threading
import time
from redis import Redis
from rq import Queue, Worker
from packages.assistant.jobs import dispatch_pending_ingestion_jobs, purge_expired_assistant_memory
from packages.database.sessions import SessionLocal
from packages.database.models.career import EventOutbox
from sqlalchemy import select, func
from packages.ops.alerts import summarize_operational_health
from packages.ops.metrics import OUTBOX_OLDEST_AGE, EVENT_DLQ_BACKLOG, OPERATIONAL_ALERTS

logger = logging.getLogger(__name__)

def _assistant_dispatch_loop(redis_url: str) -> None:
    last_purge = 0.0
    last_alert = 0.0
    while True:
        try:
            dispatch_pending_ingestion_jobs(redis_url, batch_size=20)
        except Exception:
            logger.exception("Assistant ingestion outbox dispatch failed")
        if time.time() - last_purge >= 3600:
            try:
                purge_expired_assistant_memory()
                last_purge = time.time()
            except Exception:
                logger.exception("Assistant memory retention purge failed")
        if time.time() - last_alert >= 60:
            try:
                with SessionLocal() as db:
                    pending = db.scalars(select(EventOutbox).where(
                        EventOutbox.status.in_(("pending", "retry", "processing"))
                    ).order_by(EventOutbox.created_at).limit(1)).first()
                    backlog = db.scalar(select(func.count()).select_from(EventOutbox).where(
                        EventOutbox.status.in_(("pending", "retry", "processing"))
                    )) or 0
                    dead = db.scalar(select(func.count()).select_from(EventOutbox).where(
                        EventOutbox.status == "dead_letter"
                    )) or 0
                    age = max(0.0, time.time() - pending.created_at.timestamp()) if pending else 0.0
                OUTBOX_OLDEST_AGE.set(age)
                EVENT_DLQ_BACKLOG.set(dead)
                report = summarize_operational_health({
                    "outbox_backlog": backlog, "oldest_pending_seconds": age,
                    "dead_letter_count": dead, "dependencies": {"redis": "ok"},
                })
                if report["alerts"]:
                    for alert in report["alerts"]:
                        OPERATIONAL_ALERTS.labels(alert["name"], alert["severity"]).inc()
                    logger.warning("jobseeker.operational_alerts", extra=report)
                last_alert = time.time()
            except Exception:
                logger.exception("Operational alert evaluation failed")
        time.sleep(15)

def main():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    conn = Redis.from_url(redis_url)
    dispatcher = threading.Thread(target=_assistant_dispatch_loop, args=(redis_url,),
                                  name="assistant-outbox-dispatcher", daemon=True)
    dispatcher.start()
    queues = [Queue(name, connection=conn)
              for name in ("default", "ai", "assistant", "email", "discovery")]
    Worker(queues, connection=conn).work(with_scheduler=True)

if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    main()
