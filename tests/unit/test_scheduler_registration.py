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
    assert first["registered"] == 3
    assert second["registered"] == 0
    assert second["existing"] == 3
    assert {job.id for job in scheduler.jobs} == {
        "jobseeker-interview-reminders", "jobseeker-saved-search-discovery", "jobseeker-ai-reservation-cleanup"
    }

def test_saved_search_discovery_respects_global_pause(monkeypatch):
    from apps.api.app.core.config import get_settings
    from packages.automation.tasks import run_saved_search_discovery
    settings = get_settings()
    monkeypatch.setattr(settings, "global_automation_paused", True)
    result = run_saved_search_discovery()
    assert result["paused"] is True
    assert result["searches"] == 0
