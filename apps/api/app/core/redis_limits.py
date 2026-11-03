from time import monotonic
from collections import defaultdict
from redis import Redis
from redis.exceptions import RedisError
from fastapi import HTTPException
from apps.api.app.core.config import get_settings

_local_events = defaultdict(list)

def enforce_rate_limit(key: str, limit: int = 60, window_seconds: int = 60) -> None:
    settings = get_settings()
    try:
        client = Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)
        bucket = int(__import__("time").time() // window_seconds)
        count = client.incr(f"jobseeker:rate:{bucket}:{key}")
        if count == 1:
            client.expire(f"jobseeker:rate:{bucket}:{key}", window_seconds + 2)
        if count > limit:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        return
    except HTTPException:
        raise
    except RedisError:
        if settings.app_env not in {"local", "test"}:
            raise HTTPException(status_code=503, detail="Rate limiting service unavailable")
    now = monotonic()
    events = [stamp for stamp in _local_events[key] if now - stamp < window_seconds]
    if len(events) >= limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    events.append(now)
    _local_events[key] = events
