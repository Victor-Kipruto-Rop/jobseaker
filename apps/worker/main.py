"""JobSeeker worker entry point with a durable assistant outbox dispatcher."""
from __future__ import annotations
import logging
import os
import threading
import time
from redis import Redis
from rq import Queue, Worker
from packages.assistant.jobs import dispatch_pending_ingestion_jobs

logger = logging.getLogger(__name__)

def _assistant_dispatch_loop(redis_url: str) -> None:
    while True:
        try:
            dispatch_pending_ingestion_jobs(redis_url, batch_size=20)
        except Exception:
            logger.exception("Assistant ingestion outbox dispatch failed")
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
