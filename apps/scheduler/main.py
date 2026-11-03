import os
import time
from datetime import datetime, timedelta, timezone
from redis import Redis
from rq import Queue
from rq_scheduler import Scheduler
from packages.automation.tasks import create_upcoming_interview_reminders, run_saved_search_discovery

def main():
    connection = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    queue = Queue("discovery", connection=connection)
    scheduler = Scheduler(queue=queue, connection=connection)
    if connection.set("jobseeker:scheduler:initialized", "1", nx=True):
        now = datetime.now(timezone.utc)
        scheduler.schedule(scheduled_time=now + timedelta(seconds=10),
                           func=create_upcoming_interview_reminders, interval=3600)
        scheduler.schedule(scheduled_time=now + timedelta(minutes=2),
                           func=run_saved_search_discovery, interval=21600)
    while True:
        scheduler.enqueue_jobs()
        time.sleep(15)

if __name__ == "__main__":
    main()
