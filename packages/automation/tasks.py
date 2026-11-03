import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from packages.database.sessions import SessionLocal
from packages.database.models.career import CandidateOpportunity, Interview, Notification, SavedSearch
from packages.integrations.job_boards.connectors import discover_greenhouse, discover_lever

def run_saved_search_discovery():
    """Run only explicitly configured saved searches against supported public APIs."""
    with SessionLocal() as db:
        searches = db.scalars(select(SavedSearch)).all()
        summary = {"searches": 0, "saved": 0, "duplicates": 0, "failed": 0}
        for saved_search in searches:
            config = saved_search.query or {}
            source, board = config.get("source"), config.get("board")
            if source not in {"greenhouse", "lever"} or not board:
                continue
            summary["searches"] += 1
            try:
                items = asyncio.run(discover_greenhouse(board, 100) if source == "greenhouse"
                                    else discover_lever(board, 100))
                inserted = 0
                for item in items:
                    url = item.get("source_url", "")
                    if not url or db.scalar(select(CandidateOpportunity.id).where(
                        CandidateOpportunity.user_id == saved_search.user_id,
                        CandidateOpportunity.source_url == url)):
                        summary["duplicates"] += 1
                        continue
                    if config.get("company_name"):
                        item["company"] = config["company_name"]
                    db.add(CandidateOpportunity(user_id=saved_search.user_id, **item))
                    inserted += 1
                if inserted:
                    db.add(Notification(user_id=saved_search.user_id,
                        title="New jobs found", body=f"{inserted} new roles were added from {board}."))
                db.commit()
                summary["saved"] += inserted
            except Exception:
                db.rollback()
                summary["failed"] += 1
        return summary

def create_upcoming_interview_reminders():
    """Create in-app reminders for interviews starting within the next 24 hours."""
    now = datetime.now(timezone.utc)
    until = now + timedelta(hours=24)
    with SessionLocal() as db:
        interviews = db.scalars(select(Interview).where(
            Interview.scheduled_at >= now, Interview.scheduled_at <= until)).all()
        created = 0
        for interview in interviews:
            marker = f"interview:{interview.id}"
            exists = db.scalar(select(Notification.id).where(
                Notification.user_id == interview.user_id, Notification.body == marker))
            if exists:
                continue
            db.add(Notification(user_id=interview.user_id, title="Upcoming interview",
                body=marker + f" Your {interview.interview_type} interview is scheduled for {interview.scheduled_at.isoformat()}."))
            created += 1
        db.commit()
        return {"reminders_created": created}
