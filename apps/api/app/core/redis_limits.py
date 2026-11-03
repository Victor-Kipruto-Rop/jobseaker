from time import monotonic
from collections import defaultdict
from functools import lru_cache
from threading import Lock
import time
from redis import Redis
from redis.exceptions import RedisError
from fastapi import HTTPException
from apps.api.app.core.config import get_settings

_local_events = defaultdict(list)
_local_lock = Lock()
_last_local_prune = 0.0
_INCREMENT_WITH_EXPIRY = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
"""

@lru_cache(maxsize=4)
def _redis_client(url: str) -> Redis:
    return Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)

def _enforce_local_limit(key: str, limit: int, window_seconds: int) -> None:
    global _last_local_prune
    now = monotonic()
    with _local_lock:
        if now - _last_local_prune >= 60:
            expired = [bucket for bucket, stamps in _local_events.items()
                       if not stamps or now - stamps[-1] >= 3600]
            for bucket in expired:
                _local_events.pop(bucket, None)
            _last_local_prune = now
        events = [stamp for stamp in _local_events.get(key, [])
                  if now - stamp < window_seconds]
        if len(events) >= limit:
            _local_events[key] = events
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        events.append(now)
        _local_events[key] = events

def enforce_rate_limit(key: str, limit: int = 60, window_seconds: int = 60) -> None:
    settings = get_settings()
    try:
        client = _redis_client(settings.redis_url)
        bucket = int(time.time() // window_seconds)
        redis_key = f"jobseeker:rate:{window_seconds}:{bucket}:{key}"
        count = int(client.eval(_INCREMENT_WITH_EXPIRY, 1, redis_key, window_seconds + 2))
        if count > limit:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        return
    except HTTPException:
        raise
    except RedisError as exc:
        if settings.app_env not in {"local", "development", "test"}:
            raise HTTPException(status_code=503, detail="Rate limiting service unavailable") from exc
    _enforce_local_limit(key, limit, window_seconds)
