from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from redis.exceptions import RedisError
from apps.api.app.core import redis_limits

class FakeRedis:
    def __init__(self):
        self.counts = {}
    def eval(self, script, number_of_keys, key, expiry):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

def test_redis_rate_limit_uses_atomic_increment_and_expiry(monkeypatch):
    client = FakeRedis()
    monkeypatch.setattr(redis_limits, "get_settings",
        lambda: SimpleNamespace(redis_url="redis://test", app_env="production"))
    monkeypatch.setattr(redis_limits, "_redis_client", lambda url: client)
    redis_limits.enforce_rate_limit("user:1", limit=2, window_seconds=60)
    redis_limits.enforce_rate_limit("user:1", limit=2, window_seconds=60)
    with pytest.raises(HTTPException) as error:
        redis_limits.enforce_rate_limit("user:1", limit=2, window_seconds=60)
    assert error.value.status_code == 429

def test_production_fails_closed_when_redis_is_unavailable(monkeypatch):
    monkeypatch.setattr(redis_limits, "get_settings",
        lambda: SimpleNamespace(redis_url="redis://test", app_env="production"))
    def unavailable(url):
        raise RedisError("redis unavailable")
    monkeypatch.setattr(redis_limits, "_redis_client", unavailable)
    with pytest.raises(HTTPException) as error:
        redis_limits.enforce_rate_limit("user:2")
    assert error.value.status_code == 503

def test_local_fallback_enforces_limit(monkeypatch):
    monkeypatch.setattr(redis_limits, "_local_events", __import__("collections").defaultdict(list))
    redis_limits._last_local_prune = 0
    redis_limits._enforce_local_limit("local-test", limit=1, window_seconds=60)
    with pytest.raises(HTTPException) as error:
        redis_limits._enforce_local_limit("local-test", limit=1, window_seconds=60)
    assert error.value.status_code == 429
