from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import desc, inspect, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from apps.api.app.core.redis_limits import enforce_rate_limit
from packages.events.kafka import publish_event
from apps.api.app.dependencies import get_current_user, get_db
from packages.ai.agents.job_matching.agent import JOB_SKILL_TAXONOMY
from packages.database.models.identity import User
from packages.database.models.career import (
    Application, CandidateOpportunity, CandidateProfile, CandidateSkill,
    Company, RecommendationInteraction, ResumeDocument,
)
from packages.recommendations.engine import (
    document_text, item_key, rank_opportunities, semantic_embeddings,
)

router = APIRouter()
EVENT_TYPES = {"impression", "view", "click", "save", "dismiss", "skip", "apply", "interview", "offer"}
SOURCES = {"content", "collaborative", "semantic", "graph", "fresh"}
MAX_INTERACTION_BATCH = 50


class InteractionInput(BaseModel):
    event_type: Literal[
        "impression", "view", "click", "save", "dismiss", "skip",
        "apply", "interview", "offer",
    ]
    item_key: str | None = Field(default=None, min_length=1, max_length=2200)
    opportunity_id: int | None = Field(default=None, gt=0)
    recommendation_source: str = Field(default="", max_length=40)
    position: int | None = Field(default=None, ge=0, le=500)
    dwell_seconds: float | None = Field(default=None, ge=0, le=86400)
    feature_snapshot: dict = Field(default_factory=dict)

    @field_validator("recommendation_source")
    @classmethod
    def source_is_known(cls, value: str) -> str:
        if value and value not in SOURCES:
            raise ValueError("Unknown recommendation source")
        return value

    @field_validator("feature_snapshot")
    @classmethod
    def feature_snapshot_is_bounded(cls, value: dict) -> dict:
        if len(str(value)) > 6000:
            raise ValueError("Recommendation feature snapshot is too large")
        return value


class InteractionBatch(BaseModel):
    events: list[InteractionInput] = Field(min_length=1, max_length=MAX_INTERACTION_BATCH)


def _profile_payload(profile: CandidateProfile | None) -> dict:
    if profile is None:
        return {"headline": "", "summary": "", "location": "", "target_roles": [],
                "preferences": {}, "profile_data": {}}
    return {
        "headline": profile.headline or "",
        "summary": profile.summary or "",
        "location": profile.location or "",
        "target_roles": profile.target_roles or [],
        "preferences": profile.preferences or {},
        "profile_data": profile.profile_data or {},
    }


def _extract_resume_skills(resume_text: str) -> list[str]:
    source = (resume_text or "").lower()
    found = []
    for skill in JOB_SKILL_TAXONOMY:
        pattern = r"(?<![a-z0-9])" + re.escape(skill.lower()) + r"(?![a-z0-9])"
        if re.search(pattern, source):
            found.append(skill)
    return found


def _public_job(row: CandidateOpportunity, company: Company | None = None) -> dict:
    return {
        "id": row.id,
        "owned_opportunity_id": row.id,
        "owner_user_id": row.user_id,
        "title": row.title,
        "company": row.company,
        "company_id": row.company_id,
        "company_website": row.company_website or (company.website if company else ""),
        "company_domain": row.company_domain or (company.domain if company else ""),
        "company_logo_url": row.company_logo_url or (company.logo_url if company else ""),
        "company_favicon_url": row.company_favicon_url or (company.favicon_url if company else ""),
        "company_description": row.company_description or (company.description if company else ""),
        "company_brand_color": row.company_brand_color or (company.brand_color if company else ""),
        "company_industry": company.industry if company else "",
        "company_headquarters": company.headquarters if company else "",
        "company_social_links": company.social_links if company else {},
        "source_name": row.source_name,
        "source_url": row.source_url,
        "location": row.location,
        "employment_type": row.employment_type,
        "remote_type": row.remote_type,
        "salary_min": row.salary_min,
        "salary_max": row.salary_max,
        "required_skills": row.required_skills or [],
        "description": row.description or "",
        "posted_at": row.posted_at,
        "application_deadline": row.application_deadline,
        "availability_status": row.availability_status,
        "semantic_embedding": row.semantic_embedding or [],
        "embedding_model": row.embedding_model or "",
    }


def _pgvector_scores(db: Session, user_id: int, embedding: list[float]) -> dict[tuple[int, int], float]:
    """Use native pgvector nearest-neighbor ranking when migration 0013 enabled it."""
    if not embedding or db.get_bind().dialect.name != "postgresql":
        return {}
    try:
        columns = {column["name"] for column in inspect(db.get_bind()).get_columns("candidate_opportunities")}
        if "semantic_vector" not in columns:
            return {}
        vector = "[" + ",".join(f"{float(value):.8f}" for value in embedding) + "]"
        rows = db.execute(text("""
            SELECT user_id, id, 1 - (semantic_vector <=> CAST(:vector AS vector)) AS similarity
            FROM candidate_opportunities
            WHERE availability_status = 'active' AND semantic_vector IS NOT NULL
            ORDER BY semantic_vector <=> CAST(:vector AS vector)
            LIMIT 800
        """), {"vector": vector}).all()
        return {(int(row[0]), int(row[1])): max(0.0, min(float(row[2]), 1.0)) for row in rows}
    except (SQLAlchemyError, KeyError, TypeError, ValueError):
        # The portable JSON embedding path remains available if pgvector is absent.
        return {}


@router.get("")
def get_recommendations(
    request: Request,
    limit: int = Query(default=30, ge=1, le=100),
    refresh_embeddings: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_rate_limit(f"recommendations:{user.id}", limit=30, window_seconds=60)
    now = datetime.now(timezone.utc)
    profile_row = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    profile = _profile_payload(profile_row)
    skills_rows = db.scalars(select(CandidateSkill).where(CandidateSkill.user_id == user.id)).all()
    skills = [row.skill_name for row in skills_rows]
    resume = db.scalar(select(ResumeDocument).where(
        ResumeDocument.user_id == user.id
    ).order_by(ResumeDocument.created_at.desc()).limit(1))
    resume_text = resume.extracted_text if resume else ""
    skills = list(dict.fromkeys(skills + _extract_resume_skills(resume_text)))
    profile_data = profile.get("profile_data") or {}
    target_roles = profile.get("target_roles") or profile_data.get("target_roles") or []
    if not target_roles:
        # Derive role intent only when the candidate's own CV/headline contains it.
        candidate_text = (profile.get("headline", "") + " " + resume_text[:12000]).lower()
        known_roles = (
            "data engineer", "analytics engineer", "data pipeline architect",
            "data platform engineer", "data analyst", "business intelligence analyst",
        )
        target_roles = [role.title() for role in known_roles if role in candidate_text]
    profile["target_roles"] = target_roles

    # Public job records from supported ATS sources form a shared discovery pool.
    # Only public vacancy/company fields are used; another candidate's private
    # application status, notes, profile or identity are never selected or returned.
    rows = db.scalars(select(CandidateOpportunity).where(
        CandidateOpportunity.availability_status == "active",
        CandidateOpportunity.source_url != "",
        (
            CandidateOpportunity.source_name.in_(("greenhouse", "lever"))
            | (CandidateOpportunity.user_id == user.id)
        ),
    ).order_by(desc(CandidateOpportunity.posted_at), desc(CandidateOpportunity.created_at)).limit(6000)).all()
    if not rows:
        return {
            "items": [], "profile": {"target_roles": target_roles, "skills": skills,
            "location": profile.get("location"), "resume_available": bool(resume)},
            "algorithms": {"content": "active", "collaborative": "warming_up",
                           "semantic": "optional_dependency_required", "graph": "active",
                           "learning_to_rank": "warming_up", "bandits": "active"},
            "data_quality": {"public_opportunities": 0, "profile_skill_count": len(skills)},
        }

    company_ids = {row.company_id for row in rows if row.company_id}
    company_map = {}
    if company_ids:
        company_rows = db.scalars(select(Company).where(Company.id.in_(company_ids))).all()
        company_map = {company.id: company for company in company_rows}

    # Deduplicate source listings across candidate accounts before ranking.
    deduped: dict[str, dict] = {}
    for row in rows:
        company = company_map.get(row.company_id)
        job = _public_job(row, company)
        key = item_key(job)
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = job
        elif row.user_id == user.id and existing.get("owner_user_id") != user.id:
            deduped[key] = job
    jobs = list(deduped.values())
    if not jobs:
        return {"items": [], "profile": {"target_roles": target_roles, "skills": skills},
                "algorithms": {}, "data_quality": {"public_opportunities": 0}}

    events_rows = db.scalars(select(RecommendationInteraction).where(
        RecommendationInteraction.created_at >= now - timedelta(days=120)
    ).order_by(desc(RecommendationInteraction.created_at)).limit(50000)).all()
    events = [{
        "user_id": row.user_id, "item_key": row.item_key, "event_type": row.event_type,
        "recommendation_source": row.recommendation_source,
        "feature_snapshot": row.feature_snapshot or {},
    } for row in events_rows]
    training_samples = []
    for event in events:
        if event["event_type"] in {"save", "apply", "interview", "offer", "dismiss", "skip"}:
            snapshot = event.get("feature_snapshot") or {}
            if snapshot:
                training_samples.append({
                    "label": event["event_type"] in {"save", "apply", "interview", "offer"},
                    "features": snapshot,
                })

    # Generate local 384-dimensional Sentence-Transformer embeddings when the
    # optional ML extra is installed; otherwise use the deterministic TF-IDF path.
    texts = [(" ".join(target_roles) + " " + profile.get("headline", "") + " " +
              profile.get("summary", "") + " " + " ".join(skills) + " " + resume_text[:12000))]
    texts.extend(document_text(job) for job in jobs)
    embeddings = semantic_embeddings(texts)
    semantic_ready = len(embeddings) == len(texts)
    pg_scores = _pgvector_scores(db, user.id, embeddings[0]) if semantic_ready else {}
    if semantic_ready:
        for index, job in enumerate(jobs):
            job["semantic_embedding"] = embeddings[index + 1]
            job["_profile_embedding"] = embeddings[0]
            job["embedding_model"] = "sentence-transformers/all-MiniLM-L6-v2"
            owner_id = job.get("owner_user_id")
            row_id = job.get("owned_opportunity_id")
            if owner_id and row_id:
                source_row = next((r for r in rows if r.id == row_id and r.user_id == owner_id), None)
                text_hash = hashlib.sha256(document_text(job).encode("utf-8")).hexdigest()
                if source_row and (
                    refresh_embeddings or source_row.embedding_model != job["embedding_model"]
                    or not source_row.semantic_embedding
                    or source_row.embedding_text_hash != text_hash
                ):
                    source_row.semantic_embedding = embeddings[index + 1]
                    source_row.embedding_model = job["embedding_model"]
                    source_row.embedding_text_hash = text_hash
                    if (owner_id, row_id) in pg_scores:
                        pass
                    # pgvector storage is populated when the optional native column exists.
                    try:
                        columns = {column["name"] for column in inspect(db.get_bind()).get_columns("candidate_opportunities")}
                        if "semantic_vector" in columns:
                            vector = "[" + ",".join(f"{float(v):.8f}" for v in embeddings[index + 1]) + "]"
                            db.execute(text(
                                "UPDATE candidate_opportunities SET semantic_vector = CAST(:vector AS vector) "
                                "WHERE user_id = :owner_id AND id = :row_id"
                            ), {"vector": vector, "owner_id": owner_id, "row_id": row_id})
                    except SQLAlchemyError:
                        pass

    # Merge native pgvector scores into the portable ranker features.
    for job in jobs:
        owner = job.get("owner_user_id")
        owned_id = job.get("owned_opportunity_id")
        if owner and owned_id and (owner, owned_id) in pg_scores:
            job["_pgvector_similarity"] = pg_scores[(owner, owned_id)]

    ranked = rank_opportunities(
        user.id, profile, skills, resume_text, jobs, events, training_samples,
    )
    # User-owned library IDs are returned only for this account. Cross-account
    # public roles have no local id until the candidate explicitly saves them.
    owned_by_key = {
        item_key(_public_job(row, company_map.get(row.company_id))): row.id
        for row in rows if row.user_id == user.id
    }
    items = []
    for position, job in enumerate(ranked[:limit]):
        job["opportunity_id"] = owned_by_key.get(job["item_key"])
        job.pop("owner_user_id", None)
        job.pop("owned_opportunity_id", None)
        job.pop("semantic_embedding", None)
        job.pop("embedding_model", None)
        job.pop("_pgvector_similarity", None)
        job["feature_snapshot"] = job.pop("features", {})
        job["position"] = position
        items.append(job)

    # Persist embedding backfills and leave explicit impression logging to the client.
    if semantic_ready:
        db.commit()
    return {
        "items": items,
        "profile": {
            "headline": profile.get("headline"), "target_roles": target_roles,
            "skills": skills, "location": profile.get("location"),
            "work_mode": (profile.get("preferences") or {}).get("work_mode", "not specified"),
            "resume_available": bool(resume), "profile_skill_count": len(skills),
        },
        "algorithms": {
            "user_based_cf": "active" if len(events) >= 10 else "warming_up",
            "item_based_cf": "active" if len(events) >= 10 else "warming_up",
            "tfidf_cosine": "active",
            "sentence_transformers": "active" if semantic_ready else "optional_dependency_required",
            "pgvector": "active" if bool(pg_scores) else "JSON_or_in_memory_fallback",
            "knowledge_graph": "active",
            "lightgbm_ltr": "trained" if len(training_samples) >= 40 else "warming_up",
            "thompson_sampling": "active",
            "ucb1": "active",
        },
        "data_quality": {
            "public_opportunities": len(jobs), "behavioral_events": len(events),
            "labeled_training_events": len(training_samples),
            "profile_skill_count": len(skills), "resume_available": bool(resume),
            "semantic_model_available": semantic_ready,
        },
        "disclaimer": "Recommendations estimate relevance from your profile, public job text and aggregated interaction signals. They do not predict hiring outcomes.",
    }


@router.post("/impressions", status_code=201)
async def record_impressions(
    body: InteractionBatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Batch-write recommendation exposures for unbiased bandit denominators."""
    enforce_rate_limit(f"recommendation-impressions:{user.id}", limit=30, window_seconds=60)
    rows = []
    for event in body.events:
        if event.event_type != "impression":
            raise HTTPException(status_code=422, detail="Only impression events are accepted in this batch")
        if not event.item_key:
            raise HTTPException(status_code=422, detail="Every impression requires an item_key")
        rows.append(RecommendationInteraction(
            user_id=user.id, item_key=event.item_key, event_type="impression",
            recommendation_source=event.recommendation_source, position=event.position,
            feature_snapshot=event.feature_snapshot,
        ))
    db.add_all(rows)
    db.commit()
    await publish_event("user.activity", {
        "user_id": user.id, "event_type": "impression_batch",
        "count": len(rows), "item_keys": [row.item_key for row in rows],
    }, key=str(user.id))
    return {"status": "recorded", "count": len(rows)}


@router.post("/interactions", status_code=201)
async def record_interaction(
    body: InteractionInput,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_rate_limit(f"recommendation-events:{user.id}", limit=180, window_seconds=60)
    row = None
    key = body.item_key
    if body.opportunity_id:
        row = db.scalar(select(CandidateOpportunity).where(
            CandidateOpportunity.id == body.opportunity_id,
            CandidateOpportunity.user_id == user.id,
        ))
        if not row:
            raise HTTPException(status_code=404, detail="Opportunity not found")
        key = item_key({"source_url": row.source_url, "title": row.title,
                        "company": row.company, "location": row.location})
    if not key:
        raise HTTPException(status_code=422, detail="An item_key or owned opportunity_id is required")
    if body.event_type in {"save", "apply"}:
        existing = db.scalar(select(CandidateOpportunity).where(
            CandidateOpportunity.user_id == user.id,
            CandidateOpportunity.source_url == key,
        )) if key.startswith("http") else None
        if existing is None and key.startswith("http"):
            source = db.scalar(select(CandidateOpportunity).where(
                CandidateOpportunity.source_url == key,
                CandidateOpportunity.availability_status == "active",
            ).order_by(desc(CandidateOpportunity.created_at)).limit(1))
            if source:
                source_company = db.scalar(select(Company).where(
                    Company.id == source.company_id, Company.user_id == source.user_id,
                )) if source.company_id else None
                local_company = None
                if source_company:
                    local_company = db.scalar(select(Company).where(
                        Company.user_id == user.id,
                        Company.source_provider == source_company.source_provider,
                        Company.source_board == source_company.source_board,
                    ))
                    if local_company is None:
                        local_company = Company(
                            user_id=user.id, name=source_company.name,
                            website=source_company.website, domain=source_company.domain,
                            careers_url=source_company.careers_url,
                            description=source_company.description, industry=source_company.industry,
                            headquarters=source_company.headquarters, logo_url=source_company.logo_url,
                            favicon_url=source_company.favicon_url, brand_color=source_company.brand_color,
                            source_provider=source_company.source_provider,
                            source_board=source_company.source_board, source_url=source_company.source_url,
                            social_links=source_company.social_links or {},
                            evidence=source_company.evidence or {},
                        )
                        db.add(local_company)
                        db.flush()
                existing = CandidateOpportunity(
                    user_id=user.id, title=source.title, company=source.company,
                    company_id=local_company.id if local_company else None,
                    company_website=source.company_website, company_domain=source.company_domain,
                    company_logo_url=source.company_logo_url,
                    company_favicon_url=source.company_favicon_url,
                    company_description=source.company_description,
                    company_brand_color=source.company_brand_color,
                    company_brand_source=source.company_brand_source,
                    description=source.description, source_name=source.source_name,
                    source_url=source.source_url, location=source.location,
                    employment_type=source.employment_type, remote_type=source.remote_type,
                    salary_min=source.salary_min, salary_max=source.salary_max,
                    required_skills=source.required_skills or [], posted_at=source.posted_at,
                    application_deadline=source.application_deadline,
                    availability_status="active", last_seen_at=datetime.now(timezone.utc),
                    semantic_embedding=source.semantic_embedding or [],
                    embedding_model=source.embedding_model or "",
                    embedding_text_hash=source.embedding_text_hash or "",
                )
                db.add(existing)
                db.flush()
        if existing:
            row = existing
            key = item_key({"source_url": row.source_url, "title": row.title,
                            "company": row.company, "location": row.location})
    snapshot = body.feature_snapshot
    if not snapshot and body.event_type in {"click", "save", "apply", "dismiss", "skip"}:
        previous = db.scalar(select(RecommendationInteraction).where(
            RecommendationInteraction.user_id == user.id,
            RecommendationInteraction.item_key == key,
            RecommendationInteraction.event_type == "impression",
        ).order_by(desc(RecommendationInteraction.created_at)).limit(1))
        snapshot = previous.feature_snapshot if previous else {}
    event = RecommendationInteraction(
        user_id=user.id, opportunity_id=row.id if row else (body.opportunity_id if body.opportunity_id else None),
        item_key=key, event_type=body.event_type,
        recommendation_source=body.recommendation_source,
        position=body.position, dwell_seconds=body.dwell_seconds,
        feature_snapshot=snapshot,
    )
    db.add(event)
    db.commit()
    await publish_event("user.activity", {
        "user_id": user.id, "event_id": event.id, "item_key": key,
        "event_type": body.event_type, "recommendation_source": body.recommendation_source,
        "position": body.position,
    }, key=str(user.id))
    return {"status": "recorded", "event_id": event.id,
            "opportunity_id": row.id if row else (body.opportunity_id if body.opportunity_id else None),
            "item_key": key}
