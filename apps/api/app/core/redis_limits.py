from collections import defaultdict
from functools import lru_cache
from threading import Lock
from time import monotonic, time
from uuid import uuid4
from typing import cast

from fastapi import HTTPException
from redis import Redis
from redis.exceptions import RedisError

from apps.api.app.core.config import get_settings


_local_events: dict[str, list[float]] = defaultdict(list)
_local_lock = Lock()
_last_local_prune = 0.0
_SLIDING_WINDOW = """
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - window)
local count = redis.call('ZCARD', KEYS[1])
if count >= limit then
    return limit + 1
end
redis.call('ZADD', KEYS[1], now, ARGV[4])
redis.call('PEXPIRE', KEYS[1], window + 1000)
return count + 1
"""


@lru_cache(maxsize=4)
def _redis_client(url: str) -> Redis:
    return Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)


def _enforce_local_limit(key: str, limit: int, window_seconds: int) -> None:
    global _last_local_prune
    now = monotonic()
    with _local_lock:
        if now - _last_local_prune >= 60:
            expired = [
                bucket
                for bucket, stamps in _local_events.items()
                if not stamps or now - stamps[-1] >= 3600
            ]
            for bucket in expired:
                _local_events.pop(bucket, None)
            _last_local_prune = now
        events = [
            stamp
            for stamp in _local_events.get(key, [])
            if now - stamp < window_seconds
        ]
        if len(events) >= limit:
            _local_events[key] = events
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        events.append(now)
        _local_events[key] = events


def enforce_rate_limit(key: str, limit: int = 60, window_seconds: int = 60) -> None:
    settings = get_settings()
    try:
        client = _redis_client(settings.redis_url)
        now_ms = int(time() * 1000)
        redis_key = f"jobseeker:rate:sliding:{key}"
        result = client.eval(
            _SLIDING_WINDOW,
            1,
            redis_key,
            str(now_ms),
            str(window_seconds * 1000),
            str(limit),
            f"{now_ms}:{uuid4().hex}",
        )
        count = int(cast(str, result))
        if count > limit:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        return
    except HTTPException:
        raise
    except RedisError as exc:
        if settings.app_env not in {"local", "development", "test"}:
            raise HTTPException(
                status_code=503, detail="Rate limiting service unavailable"
            ) from exc
    _enforce_local_limit(key, limit, window_seconds)
