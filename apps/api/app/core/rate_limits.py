from collections import defaultdict
from time import monotonic
class InMemoryRateLimiter:
    """Single-process development limiter. Use Redis-backed limits in multi-worker deployments."""
    def __init__(self,limit=60,window_seconds=60):
        self.limit=limit; self.window_seconds=window_seconds; self.events=defaultdict(list)
    def allow(self,key):
        now=monotonic()
        self.events[key]=[t for t in self.events[key] if now-t<self.window_seconds]
        if len(self.events[key])>=self.limit: return False
        self.events[key].append(now); return True
