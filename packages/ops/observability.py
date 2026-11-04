"""Optional OpenTelemetry tracing setup for API and database requests."""
from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger(__name__)


def configure_telemetry(app: Any) -> bool:
    """Enable OTLP traces when configured; do not break startup if optional extras are absent."""
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
        logger.exception("OpenTelemetry instrumentation could not be initialized")
        return False
