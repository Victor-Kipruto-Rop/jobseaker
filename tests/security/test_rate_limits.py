import pytest
from fastapi import HTTPException
from redis.exceptions import RedisError
from apps.api.app.core import redis_limits

def test_local_rate_limit_blocks_after_limit(monkeypatch):
    from apps.api.app.core.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "app_env", "test")
    monkeypatch.setattr(redis_limits, "_redis_client",
        lambda _url: (_ for _ in ()).throw(RedisError("redis unavailable")))
    key = "test-security-limit"
    redis_limits._local_events.pop(key, None)
    for _ in range(2):
        redis_limits.enforce_rate_limit(key, limit=2, window_seconds=60)
    with pytest.raises(HTTPException) as error:
        redis_limits.enforce_rate_limit(key, limit=2, window_seconds=60)
    assert error.value.status_code == 429
