import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from packages.database.sessions import SessionLocal
from packages.database.models.entities import AIUsageReservation
from packages.database.models.career import (
    CandidateOpportunity,
    Interview,
    Notification,
    SavedSearch,
)
from packages.integrations.job_boards.connectors import (
    discover_greenhouse,
    discover_lever,
    filter_jobs,
)
from apps.api.app.core.config import get_settings


async def _fetch_saved_searches(searches, concurrency: int = 5):
    """Fetch external job-board data with bounded concurrency and no open DB session."""
    semaphore = asyncio.Semaphore(max(1, min(concurrency, 10)))

    async def fetch(search_id, user_id, config):
        source, board = config.get("source"), config.get("board")
        if source not in {"greenhouse", "lever"} or not board:
            return search_id, user_id, config, [], None
        async with semaphore:
            try:
                items = (
                    await discover_greenhouse(board, 100)
                    if source == "greenhouse"
                    else await discover_lever(board, 100)
                )
                return search_id, user_id, config, items, None
            except Exception as exc:
                return search_id, user_id, config, [], exc

    return await asyncio.gather(*(fetch(*item) for item in searches))


def run_saved_search_discovery():
    """Run enabled saved searches with bounded I/O concurrency and isolated DB transactions."""
    settings = get_settings()
    if settings.global_automation_paused or not settings.job_discovery_enabled:
        return {"paused": True, "searches": 0, "saved": 0, "duplicates": 0, "failed": 0}

    with SessionLocal() as db:
        rows = db.execute(
            select(SavedSearch.id, SavedSearch.user_id, SavedSearch.query)
            .order_by(SavedSearch.id.asc())
            .limit(250)
        ).all()
        searches = [(row.id, row.user_id, row.query or {}) for row in rows]

    fetched = asyncio.run(_fetch_saved_searches(searches))
    summary = {"paused": False, "searches": 0, "saved": 0, "duplicates": 0, "failed": 0}
    for search_id, user_id, config, items, error in fetched:
        source, board = config.get("source"), config.get("board")
        if source not in {"greenhouse", "lever"} or not board:
            continue
        summary["searches"] += 1
        if error is not None:
            summary["failed"] += 1
            continue
        items = filter_jobs(
            items,
            keywords=config.get("keywords"),
            location=config.get("location"),
            remote_only=bool(config.get("remote_only", False)),
        )
        inserted = 0
        try:
            with SessionLocal() as db:
                for item in items:
                    url = item.get("source_url", "")
                    if not url or db.scalar(
                        select(CandidateOpportunity.id).where(
                            CandidateOpportunity.user_id == user_id,
                            CandidateOpportunity.source_url == url,
                        )
                    ):
                        summary["duplicates"] += 1
                        continue
                    if config.get("company_name"):
                        item["company"] = config["company_name"]
                    try:
                        with db.begin_nested():
                            db.add(CandidateOpportunity(user_id=user_id, **item))
                            db.flush()
                        inserted += 1
                    except IntegrityError:
                        summary["duplicates"] += 1
                if inserted:
                    db.add(
                        Notification(
                            user_id=user_id,
                            title="New jobs found",
                            body=f"{inserted} new roles were added from {board}.",
                        )
                    )
                db.commit()
            summary["saved"] += inserted
        except SQLAlchemyError:
            summary["failed"] += 1
    return summary


def create_upcoming_interview_reminders():
    """Create idempotent in-app reminders for interviews in the next 24 hours."""
    now = datetime.now(UTC)
    until = now + timedelta(hours=24)
    with SessionLocal() as db:
        interviews = db.scalars(
            select(Interview).where(
                Interview.scheduled_at >= now,
                Interview.scheduled_at <= until,
            )
        ).all()
        created = 0
        for interview in interviews:
            scheduled_at = interview.scheduled_at
            if scheduled_at is None:
                continue
            marker = f"interview:{interview.id}"
            exists = db.scalar(
                select(Notification.id).where(
                    Notification.user_id == interview.user_id,
                    Notification.body.like(marker + "%"),
                )
            )
            if exists:
                continue
            db.add(
                Notification(
                    user_id=interview.user_id,
                    title="Upcoming interview",
                    body=(
                        marker
                        + f" Your {interview.interview_type} interview is scheduled for "
                        + f"{scheduled_at.isoformat()}."
                    ),
                )
            )
            created += 1
        db.commit()
        return {"reminders_created": created}


def cleanup_expired_ai_reservations():
    """Purge terminal or abandoned AI reservation metadata after a 30-day retention window."""
    cutoff = datetime.now(UTC) - timedelta(days=30)
    with SessionLocal() as db:
        expired_count = db.scalar(
            select(func.count())
            .select_from(AIUsageReservation)
            .where(AIUsageReservation.expires_at < cutoff)
        ) or 0
        db.execute(
            delete(AIUsageReservation).where(AIUsageReservation.expires_at < cutoff)
        )
        db.commit()
        return {"deleted_reservations": int(expired_count)}
