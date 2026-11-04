import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from apps.api.app.core.config import get_settings
from packages.database.models.entities import AIUsageReservation
from packages.database.models.career import (
    CandidateOpportunity,
    Company,
    Interview,
    Notification,
    SavedSearch,
)
from packages.database.sessions import SessionLocal
from packages.integrations.job_boards.connectors import (
    discover_company_profile,
    discover_greenhouse,
    discover_lever,
    filter_jobs,
)


async def _fetch_saved_searches(searches, concurrency: int = 5):
    """Fetch external job-board data with bounded concurrency and no open DB session."""
    semaphore = asyncio.Semaphore(max(1, min(concurrency, 10)))

    async def fetch(search_id, user_id, config):
        source, board = config.get("source"), config.get("board")
        if source not in {"greenhouse", "lever"} or not board:
            return search_id, user_id, config, [], None
        async with semaphore:
            try:
                jobs_task = (
                    discover_greenhouse(board, 100)
                    if source == "greenhouse"
                    else discover_lever(board, 100)
                )
                items, profile = await asyncio.gather(
                    jobs_task, discover_company_profile(source, board)
                )
                enriched_config = {**config, "_company_profile": profile}
                return search_id, user_id, enriched_config, items, None
            except Exception as exc:  # noqa: BLE001 - isolate failures per external job-board source
                return search_id, user_id, config, [], exc

    return await asyncio.gather(*(fetch(*item) for item in searches))


def run_saved_search_discovery():
    """Refresh saved searches, employer identity and role availability for each owner."""
    settings = get_settings()
    if settings.global_automation_paused or not settings.job_discovery_enabled:
        return {"paused": True, "searches": 0, "saved": 0, "duplicates": 0,
                "refreshed": 0, "removed": 0, "failed": 0}

    with SessionLocal() as db:
        rows = db.execute(
            select(SavedSearch.id, SavedSearch.user_id, SavedSearch.query)
            .order_by(SavedSearch.id.asc())
            .limit(250)
        ).all()
        searches = [(row.id, row.user_id, row.query or {}) for row in rows]

    fetched = asyncio.run(_fetch_saved_searches(searches))
    summary = {"paused": False, "searches": 0, "saved": 0, "duplicates": 0,
               "refreshed": 0, "removed": 0, "failed": 0}
    for search_id, user_id, config, discovered, error in fetched:
        source, board = config.get("source"), config.get("board")
        if source not in {"greenhouse", "lever"} or not board:
            continue
        summary["searches"] += 1
        if error is not None:
            summary["failed"] += 1
            continue

        profile = config.get("_company_profile") or {
            "company": (config.get("company_name") or board.replace("-", " ").title()),
            "company_website": "", "company_domain": "", "company_logo_url": "",
            "company_favicon_url": "", "company_description": "",
            "company_brand_color": "", "company_brand_source": "", "company_social_links": {},
        }
        if config.get("company_name"):
            profile["company"] = config["company_name"]
        filtered = filter_jobs(
            discovered,
            keywords=config.get("keywords"),
            location=config.get("location"),
            remote_only=bool(config.get("remote_only", False)),
        )
        seen_urls = {item.get("source_url", "") for item in discovered if item.get("source_url")}
        checked_at = datetime.now(UTC)
        inserted = 0
        refreshed = 0
        removed = 0
        try:
            with SessionLocal() as db:
                company = db.scalar(select(Company).where(
                    Company.user_id == user_id,
                    Company.source_provider == source,
                    Company.source_board == board.lower(),
                ))
                if company is None:
                    company = Company(
                        user_id=user_id, name=profile["company"],
                        source_provider=source, source_board=board.lower(),
                    )
                    db.add(company)
                    db.flush()
                company.name = profile["company"]
                company.website = profile.get("company_website") or company.website
                company.domain = profile.get("company_domain") or company.domain
                company.careers_url = profile.get("company_brand_source") or company.careers_url
                company.description = profile.get("company_description") or company.description
                company.logo_url = profile.get("company_logo_url") or company.logo_url
                company.favicon_url = profile.get("company_favicon_url") or company.favicon_url
                company.brand_color = profile.get("company_brand_color") or company.brand_color
                company.social_links = {
                    **(company.social_links or {}),
                    **(profile.get("company_social_links") or {}),
                }
                company.source_url = profile.get("company_brand_source") or company.source_url
                company.last_enriched_at = checked_at
                company.evidence = {
                    **(company.evidence or {}),
                    "provider": source,
                    "board": board.lower(),
                    "source_url": profile.get("company_brand_source", ""),
                    "last_discovered_at": checked_at.isoformat(),
                    "published_fields": [
                        key for key in (
                            "company_website", "company_logo_url", "company_favicon_url",
                            "company_description", "company_brand_color", "company_social_links",
                        ) if profile.get(key)
                    ],
                }
                if profile.get("company_brand_source") and company.verified_at is None:
                    company.verified_at = checked_at

                for item in discovered:
                    url = item.get("source_url", "")
                    if not url:
                        continue
                    existing = db.scalar(select(CandidateOpportunity).where(
                        CandidateOpportunity.user_id == user_id,
                        CandidateOpportunity.source_url == url,
                    ))
                    if existing is None:
                        continue
                    changed = False
                    if existing.availability_status != "active":
                        existing.availability_status = "active"
                        changed = True
                    existing.last_seen_at = checked_at
                    if existing.company_id is None:
                        existing.company_id = company.id
                        changed = True
                    if existing.company != profile["company"]:
                        existing.company = profile["company"]
                        changed = True
                    for key in (
                        "title", "description", "location", "employment_type",
                        "remote_type", "required_skills", "posted_at",
                    ):
                        incoming = item.get(key)
                        if incoming not in (None, "", [], "unspecified") and getattr(existing, key) != incoming:
                            setattr(existing, key, incoming)
                            changed = True
                    for key, profile_key in (
                        ("company_website", "company_website"),
                        ("company_domain", "company_domain"),
                        ("company_logo_url", "company_logo_url"),
                        ("company_favicon_url", "company_favicon_url"),
                        ("company_description", "company_description"),
                        ("company_brand_color", "company_brand_color"),
                        ("company_brand_source", "company_brand_source"),
                    ):
                        incoming = profile.get(profile_key, "")
                        if incoming and getattr(existing, key) != incoming:
                            setattr(existing, key, incoming)
                            changed = True
                    if changed:
                        refreshed += 1

                for item in filtered:
                    url = item.get("source_url", "")
                    if not url or db.scalar(select(CandidateOpportunity.id).where(
                        CandidateOpportunity.user_id == user_id,
                        CandidateOpportunity.source_url == url,
                    )):
                        summary["duplicates"] += 1
                        continue
                    imported = {
                        **item,
                        "company": profile["company"],
                        "company_id": company.id,
                        "company_website": profile.get("company_website", ""),
                        "company_domain": profile.get("company_domain", ""),
                        "company_logo_url": profile.get("company_logo_url", ""),
                        "company_favicon_url": profile.get("company_favicon_url", ""),
                        "company_description": profile.get("company_description", ""),
                        "company_brand_color": profile.get("company_brand_color", ""),
                        "company_brand_source": profile.get("company_brand_source", ""),
                        "availability_status": "active",
                        "last_seen_at": checked_at,
                    }
                    try:
                        with db.begin_nested():
                            db.add(CandidateOpportunity(user_id=user_id, **imported))
                            db.flush()
                        inserted += 1
                    except IntegrityError:
                        summary["duplicates"] += 1

                # Only a successful, under-limit response is treated as a complete board snapshot.
                if len(discovered) < 100:
                    active_roles = db.scalars(select(CandidateOpportunity).where(
                        CandidateOpportunity.user_id == user_id,
                        CandidateOpportunity.company_id == company.id,
                        CandidateOpportunity.availability_status == "active",
                    )).all()
                    for previous in active_roles:
                        if previous.source_url and previous.source_url not in seen_urls:
                            previous.availability_status = "removed"
                            removed += 1

                if inserted:
                    db.add(Notification(
                        user_id=user_id,
                        title="New jobs found",
                        body=f"{inserted} new roles were added from {profile['company']}.",
                    ))
                db.commit()
            summary["saved"] += inserted
            summary["refreshed"] += refreshed
            summary["removed"] += removed
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
