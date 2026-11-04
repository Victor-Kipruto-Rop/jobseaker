"""Threshold-based operational alerts for worker and readiness telemetry."""
from __future__ import annotations

def evaluate_operational_alerts(snapshot: dict) -> list[dict]:
    alerts = []
    backlog = int(snapshot.get("outbox_backlog") or 0)
    oldest = float(snapshot.get("oldest_pending_seconds") or 0)
    dlq = int(snapshot.get("dead_letter_count") or 0)
    retry_rate = float(snapshot.get("consumer_retry_rate") or 0)
    if backlog >= 1000:
        alerts.append({"name": "outbox_backlog_critical", "severity": "critical",
                       "value": backlog, "threshold": 1000})
    elif backlog >= 250:
        alerts.append({"name": "outbox_backlog_high", "severity": "warning",
                       "value": backlog, "threshold": 250})
    if oldest >= 900:
        alerts.append({"name": "outbox_delivery_lag", "severity": "critical",
                       "value": oldest, "threshold": 900})
    if dlq > 0:
        alerts.append({"name": "dead_letter_events", "severity": "warning",
                       "value": dlq, "threshold": 0})
    if retry_rate >= 0.10:
        alerts.append({"name": "consumer_retry_rate_high", "severity": "warning",
                       "value": retry_rate, "threshold": 0.10})
    for dependency, state in (snapshot.get("dependencies") or {}).items():
        if state != "ok":
            alerts.append({"name": f"dependency_{dependency}_unavailable",
                           "severity": "critical", "value": str(state)[:80]})
    return alerts

def summarize_operational_health(snapshot: dict) -> dict:
    alerts = evaluate_operational_alerts(snapshot)
    critical = sum(item["severity"] == "critical" for item in alerts)
    return {"status": "critical" if critical else "degraded" if alerts else "healthy",
            "alert_count": len(alerts), "alerts": alerts,
            "automatic_remediation": False}
