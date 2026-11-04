"""Process-local circuit breaker for bounded outbound provider calls."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from threading import Lock
from time import monotonic


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpen(RuntimeError):
    pass


@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    recovery_seconds: float = 30.0
    half_open_max_calls: int = 1

    def __post_init__(self):
        if self.failure_threshold < 1 or self.recovery_seconds <= 0 or self.half_open_max_calls < 1:
            raise ValueError("Invalid circuit breaker configuration")
        self._failures = 0
        self._opened_at = 0.0
        self._half_open_calls = 0
        self._state = CircuitState.CLOSED
        self._lock = Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN and monotonic() - self._opened_at >= self.recovery_seconds:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
            return self._state

    def before_call(self) -> None:
        with self._lock:
            if self._state == CircuitState.OPEN and monotonic() - self._opened_at >= self.recovery_seconds:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
            if self._state == CircuitState.OPEN:
                raise CircuitOpen("Provider circuit is open")
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitOpen("Provider circuit is probing recovery")
                self._half_open_calls += 1

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._half_open_calls = 0
            self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._state == CircuitState.HALF_OPEN or self._failures >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = monotonic()
                self._half_open_calls = 0

    def call(self, function, *args, **kwargs):
        self.before_call()
        try:
            result = function(*args, **kwargs)
        except Exception:
            self.record_failure()
            raise
        self.record_success()
        return result

    async def call_async(self, function, *args, **kwargs):
        """Await an outbound provider call under the same breaker state."""
        self.before_call()
        try:
            result = await function(*args, **kwargs)
        except Exception:
            self.record_failure()
            raise
        self.record_success()
        return result
