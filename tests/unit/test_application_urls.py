import pytest
from pydantic import ValidationError
from apps.api.app.api.v1.applications.routes import ApplicationCreate, ApplicationUpdate

def test_application_accepts_https_job_url():
    item = ApplicationCreate(role_title="Data Engineer", job_url="https://example.com/jobs/123")
    assert item.job_url.startswith("https://")

def test_application_rejects_script_url():
    with pytest.raises(ValidationError):
        ApplicationCreate(role_title="Data Engineer", job_url="javascript:alert(1)")

def test_optional_update_url_can_be_omitted():
    assert ApplicationUpdate(notes="Follow up next week").job_url is None
