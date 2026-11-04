from packages.ops.alerts import summarize_operational_health

def test_critical_backlog_and_dependency_alerts():
    result = summarize_operational_health({
        "outbox_backlog": 1500, "oldest_pending_seconds": 1200,
        "dead_letter_count": 2, "dependencies": {"redis": "error"},
    })
    assert result["status"] == "critical"
    names = {item["name"] for item in result["alerts"]}
    assert "outbox_backlog_critical" in names
    assert "outbox_delivery_lag" in names
    assert "dependency_redis_unavailable" in names

def test_healthy_snapshot_has_no_alerts():
    assert summarize_operational_health({"outbox_backlog": 0})["status"] == "healthy"
