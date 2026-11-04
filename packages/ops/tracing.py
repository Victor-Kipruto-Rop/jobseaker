"""Optional OpenTelemetry context propagation across event boundaries."""
from __future__ import annotations

from contextlib import contextmanager, nullcontext
from typing import Any, Iterator


def inject_trace_context() -> dict[str, str]:
    try:
        from opentelemetry import propagate
        carrier: dict[str, str] = {}
        propagate.inject(carrier)
        return carrier
    except ImportError:
        return {}


@contextmanager
def consume_trace_context(
    name: str, carrier: dict[str, Any] | None,
) -> Iterator[None]:
    try:
        from opentelemetry import propagate, trace
    except ImportError:
        with nullcontext():
            yield
        return
    parent = propagate.extract(carrier or {})
    tracer = trace.get_tracer("jobseeker.events")
    with tracer.start_as_current_span(name, context=parent) as span:
        span.set_attribute("messaging.system", "kafka")
        span.set_attribute("messaging.operation", "process")
        yield
