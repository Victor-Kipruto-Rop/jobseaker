"""Low-cardinality Prometheus metrics shared by API and worker processes."""
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

HTTP_REQUESTS = Counter(
    "jobseeker_http_requests_total",
    "Completed HTTP requests",
    ("method", "route", "status"),
)
HTTP_DURATION = Histogram(
    "jobseeker_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ("method", "route"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
EVENT_DELIVERY = Counter(
    "jobseeker_event_delivery_total",
    "Outbox and consumer event processing outcomes",
    ("direction", "topic", "outcome"),
)
OUTBOX_BACKLOG = Gauge(
    "jobseeker_event_outbox_backlog",
    "Number of pending, retrying or processing outbox events",
)
CONSUMER_RETRIES = Counter(
    "jobseeker_event_consumer_retries_total",
    "Kafka consumer processing retries",
    ("topic",),
)
CONSUMER_DLQ = Counter(
    "jobseeker_event_consumer_dlq_total",
    "Events routed to dead-letter topics",
    ("topic",),
)


def prometheus_payload() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
