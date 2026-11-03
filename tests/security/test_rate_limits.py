import pytest
from fastapi import HTTPException
from apps.api.app.core.redis_limits import enforce_rate_limit

def test_local_rate_limit_blocks_after_limit(monkeypatch):
    from apps.api.app.core.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "app_env", "test")
    key = "test-security-limit"
    for _ in range(2):
        enforce_rate_limit(key, limit=2, window_seconds=60)
    with pytest.raises(HTTPException) as error:
        enforce_rate_limit(key, limit=2, window_seconds=60)
    assert error.value.status_code == 429
