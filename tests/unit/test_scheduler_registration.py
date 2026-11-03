from types import SimpleNamespace
from apps.scheduler.main import ensure_recurring_jobs

class FakeLock:
    def acquire(self):
        return True
    def release(self):
        return None

class FakeRedis:
    def lock(self, *args, **kwargs):
        return FakeLock()

class FakeScheduler:
    def __init__(self):
        self.jobs = []
    def get_jobs(self):
        return list(self.jobs)
    def schedule(self, **kwargs):
        self.jobs.append(SimpleNamespace(id=kwargs["id"]))

def test_recurring_scheduler_registration_is_idempotent():
    scheduler = FakeScheduler()
    connection = FakeRedis()
    first = ensure_recurring_jobs(scheduler, connection)
    second = ensure_recurring_jobs(scheduler, connection)
    assert first["registered"] == 2
    assert second["registered"] == 0
    assert second["existing"] == 2
    assert {job.id for job in scheduler.jobs} == {
        "jobseeker-interview-reminders", "jobseeker-saved-search-discovery"
    }
