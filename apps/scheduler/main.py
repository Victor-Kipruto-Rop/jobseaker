import os
import time
from datetime import datetime, timedelta, timezone
from redis import Redis
from rq import Queue
from rq_scheduler import Scheduler
from packages.automation.tasks import create_upcoming_interview_reminders, run_saved_search_discovery

def ensure_recurring_jobs(scheduler: Scheduler, connection: Redis) -> dict:
    """Register deterministic recurring jobs without a permanent one-shot flag."""
    lock = connection.lock("jobseeker:scheduler:registration-lock", timeout=30, blocking_timeout=5)
    if not lock.acquire():
        return {"registered": 0, "existing": 0, "lock_acquired": False}
    try:
        scheduled = {job.id for job in scheduler.get_jobs()}
        now = datetime.now(timezone.utc)
        definitions = [
            ("jobseeker-interview-reminders", create_upcoming_interview_reminders,
             now + timedelta(seconds=10), 3600),
            ("jobseeker-saved-search-discovery", run_saved_search_discovery,
             now + timedelta(minutes=2), 21600),
        ]
        registered = 0
        existing = 0
        for job_id, function, first_run, interval in definitions:
            if job_id in scheduled:
                existing += 1
                continue
            scheduler.schedule(
                scheduled_time=first_run,
                func=function,
                interval=interval,
                repeat=None,
                id=job_id,
                result_ttl=-1,
                timeout=1800,
                description=job_id,
            )
            registered += 1
        return {"registered": registered, "existing": existing, "lock_acquired": True}
    finally:
        lock.release()

def main():
    connection = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    connection.ping()
    queue = Queue("discovery", connection=connection)
    scheduler = Scheduler(queue=queue, connection=connection)
    ensure_recurring_jobs(scheduler, connection)
    while True:
        scheduler.enqueue_jobs()
        time.sleep(15)

if __name__ == "__main__":
    main()
