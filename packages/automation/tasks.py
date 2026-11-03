import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, delete
from packages.database.sessions import SessionLocal
from packages.database.models.entities import AIUsageReservation
from packages.database.models.career import CandidateOpportunity, Interview, Notification, SavedSearch
from packages.integrations.job_boards.connectors import discover_greenhouse, discover_lever
from apps.api.app.core.config import get_settings

def run_saved_search_discovery():
    """Run explicitly configured saved searches without holding DB connections during HTTP calls."""
    settings = get_settings()
    if settings.global_automation_paused or not settings.job_discovery_enabled:
        return {"paused": True, "searches": 0, "saved": 0, "duplicates": 0, "failed": 0}

    with SessionLocal() as db:
        rows = db.execute(select(SavedSearch.id, SavedSearch.user_id, SavedSearch.query)
                          .order_by(SavedSearch.id.asc()).limit(50)).all()
        searches = [(row.id, row.user_id, row.query or {}) for row in rows]

    summary = {"paused": False, "searches": 0, "saved": 0, "duplicates": 0, "failed": 0}
    for search_id, user_id, config in searches:
        source, board = config.get("source"), config.get("board")
        if source not in {"greenhouse", "lever"} or not board:
            continue
        summary["searches"] += 1
        try:
            items = asyncio.run(discover_greenhouse(board, 100) if source == "greenhouse"
                                else discover_lever(board, 100))
            inserted = 0
            with SessionLocal() as db:
                for item in items:
                    url = item.get("source_url", "")
                    if not url or db.scalar(select(CandidateOpportunity.id).where(
                        CandidateOpportunity.user_id == user_id,
                        CandidateOpportunity.source_url == url)):
                        summary["duplicates"] += 1
                        continue
                    if config.get("company_name"):
                        item["company"] = config["company_name"]
                    db.add(CandidateOpportunity(user_id=user_id, **item))
                    inserted += 1
                if inserted:
                    db.add(Notification(user_id=user_id, title="New jobs found",
                        body=f"{inserted} new roles were added from {board}."))
                db.commit()
            summary["saved"] += inserted
        except Exception:
            summary["failed"] += 1
    return summary

def create_upcoming_interview_reminders():
    """Create idempotent in-app reminders for interviews in the next 24 hours."""
    now = datetime.now(timezone.utc)
    until = now + timedelta(hours=24)
    with SessionLocal() as db:
        interviews = db.scalars(select(Interview).where(
            Interview.scheduled_at >= now, Interview.scheduled_at <= until)).all()
        created = 0
        for interview in interviews:
            marker = f"interview:{interview.id}"
            exists = db.scalar(select(Notification.id).where(
                Notification.user_id == interview.user_id,
                Notification.body.like(marker + "%")))
            if exists:
                continue
            db.add(Notification(user_id=interview.user_id, title="Upcoming interview",
                body=marker + f" Your {interview.interview_type} interview is scheduled for {interview.scheduled_at.isoformat()}."))
            created += 1
        db.commit()
        return {"reminders_created": created}

def cleanup_expired_ai_reservations():
    """Purge terminal or abandoned AI reservation metadata after a 30-day retention window."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    with SessionLocal() as db:
        result = db.execute(delete(AIUsageReservation).where(
            AIUsageReservation.expires_at < cutoff))
        db.commit()
        return {"deleted_reservations": int(result.rowcount or 0)}
