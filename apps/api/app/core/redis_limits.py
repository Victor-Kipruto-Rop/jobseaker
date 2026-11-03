from time import monotonic
from collections import defaultdict
from functools import lru_cache
import time
from redis import Redis
from redis.exceptions import RedisError
from fastapi import HTTPException
from apps.api.app.core.config import get_settings

_local_events = defaultdict(list)

@lru_cache(maxsize=4)
def _redis_client(url: str) -> Redis:
    return Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)

def enforce_rate_limit(key: str, limit: int = 60, window_seconds: int = 60) -> None:
    settings = get_settings()
    try:
        client = _redis_client(settings.redis_url)
        bucket = int(time.time() // window_seconds)
        redis_key = f"jobseeker:rate:{window_seconds}:{bucket}:{key}"
        count = client.incr(redis_key)
        if count == 1:
            client.expire(redis_key, window_seconds + 2)
        if count > limit:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        return
    except HTTPException:
        raise
    except RedisError as exc:
        if settings.app_env not in {"local", "development", "test"}:
            raise HTTPException(status_code=503, detail="Rate limiting service unavailable") from exc
    now = monotonic()
    events = [stamp for stamp in _local_events[key] if now - stamp < window_seconds]
    if len(events) >= limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    events.append(now)
    _local_events[key] = events
