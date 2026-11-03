from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from apps.api.app.api.v1.opportunities import routes
from packages.automation.tasks import run_saved_search_discovery

@pytest.mark.asyncio
async def test_manual_discovery_requires_explicit_enablement(monkeypatch):
    monkeypatch.setattr(routes, "get_settings", lambda: SimpleNamespace(job_discovery_enabled=False))
    body = routes.DiscoveryRequest(source="greenhouse", board="example")
    with pytest.raises(HTTPException) as error:
        await routes.discover_jobs(body, SimpleNamespace(id=1), None)
    assert error.value.status_code == 503

def test_scheduled_discovery_requires_feature_enabled_and_global_unpaused(monkeypatch):
    monkeypatch.setattr("packages.automation.tasks.get_settings",
        lambda: SimpleNamespace(global_automation_paused=False, job_discovery_enabled=False))
    result = run_saved_search_discovery()
    assert result["paused"] is True
