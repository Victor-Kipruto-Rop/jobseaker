"""Optional OpenTelemetry tracing and metrics for API and worker processes."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)
_worker_counters: dict[str, Any] = {}


def configure_telemetry(app: Any) -> bool:
    """Enable API request/database traces when an OTLP endpoint is configured."""
    from apps.api.app.core.config import get_settings
    settings = get_settings()
    endpoint = settings.otel_exporter_otlp_endpoint
    if not endpoint:
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from packages.database.sessions import engine

        provider = TracerProvider(resource=Resource.create({
            "service.name": settings.otel_service_name,
            "deployment.environment": settings.app_env,
        }))
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
        SQLAlchemyInstrumentor().instrument(engine=engine)
        return True
    except ImportError:
        logger.warning("OTel endpoint is configured but observability extras are not installed")
        return False
    except Exception:
        logger.exception("OpenTelemetry API instrumentation could not be initialized")
        return False


def configure_worker_telemetry(service_name: str) -> bool:
    """Configure OTLP traces and low-cardinality worker counters in worker processes."""
    from apps.api.app.core.config import get_settings
    settings = get_settings()
    endpoint = settings.otel_exporter_otlp_endpoint
    if not endpoint:
        return False
    try:
        from opentelemetry import metrics, trace
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({
            "service.name": service_name,
            "deployment.environment": settings.app_env,
        })
        traces = TracerProvider(resource=resource)
        traces.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(traces)
        reader = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=endpoint))
        metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[reader]))
        meter = metrics.get_meter(service_name)
        _worker_counters["events"] = meter.create_counter(
            "jobseeker.worker.events", description="Worker event outcomes",
        )
        _worker_counters["outbox"] = meter.create_counter(
            "jobseeker.outbox.events", description="Transactional outbox relay outcomes",
        )
        return True
    except ImportError:
        logger.warning("OTel worker endpoint is configured but observability extras are missing")
        return False
    except Exception:
        logger.exception("OpenTelemetry worker instrumentation could not be initialized")
        return False


def record_worker_event(topic: str, outcome: str, *, outbox: bool = False) -> None:
    """Record bounded topic/outcome dimensions; never use user IDs as metric labels."""
    counter = _worker_counters.get("outbox" if outbox else "events")
    if counter is not None:
        counter.add(1, {"topic": topic[:80], "outcome": outcome[:40]})
