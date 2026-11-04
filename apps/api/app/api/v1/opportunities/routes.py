from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from typing import Literal
import httpx
from apps.api.app.core.redis_limits import enforce_rate_limit
from packages.integrations.job_boards.connectors import (
    discover_company_profile, discover_greenhouse, discover_lever, filter_jobs,
)
from packages.integrations.url_validation import validate_http_url
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from apps.api.app.dependencies import get_current_user, get_db
from apps.api.app.core.config import get_settings
from packages.ai.agents.job_matching.agent import score_job
from packages.database.models.identity import User
from packages.database.models.career import CandidateOpportunity, CandidateSkill

router = APIRouter()

class MatchRequest(BaseModel):
    title: str = Field(min_length=2, max_length=250)
    description: str = Field(min_length=20, max_length=20000)
    skills: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("skills")
    @classmethod
    def normalize_skills(cls, values):
        return list(dict.fromkeys(value.strip()[:120] for value in values if value.strip()))

class DiscoveryRequest(BaseModel):
    source: Literal["greenhouse", "lever"]
    board: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9-]{0,79}$")
    company_name: str | None = Field(default=None, max_length=250)
    limit: int = Field(default=50, ge=1, le=100)
    keywords: list[str] = Field(default_factory=list, max_length=20)
    location: str | None = Field(default=None, max_length=120)
    remote_only: bool = False

    @field_validator("keywords")
    @classmethod
    def normalize_keywords(cls, values):
        return list(dict.fromkeys(value.strip()[:80] for value in values if value.strip()))

class OpportunityCreate(BaseModel):
    title: str = Field(min_length=2, max_length=250)
    company: str = Field(default="", max_length=250)
    description: str = Field(default="", max_length=30000)
    company_website: str = Field(default="", max_length=1000)
    company_domain: str = Field(default="", max_length=253)
    company_logo_url: str = Field(default="", max_length=2000)
    company_favicon_url: str = Field(default="", max_length=2000)
    company_description: str = Field(default="", max_length=10000)
    company_brand_color: str = Field(default="", max_length=7, pattern=r"^$|^#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?$")
    company_brand_source: str = Field(default="", max_length=1000)
    source_name: str = Field(default="manual", max_length=100)
    source_url: str = Field(default="", max_length=2000)
    location: str = Field(default="", max_length=250)
    employment_type: str = Field(default="unspecified", max_length=60)
    remote_type: str = Field(default="unspecified", max_length=40)
    required_skills: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("required_skills")
    @classmethod
    def normalize_required_skills(cls, values):
        return list(dict.fromkeys(value.strip()[:120] for value in values if value.strip()))

    @field_validator("source_url")
    @classmethod
    def safe_source_url(cls, value):
        return validate_http_url(value)

    @field_validator("company_website", "company_logo_url", "company_favicon_url", "company_brand_source")
    @classmethod
    def secure_company_urls(cls, value):
        safe = validate_http_url(value)
        if safe and not safe.lower().startswith("https://"):
            raise ValueError("Company websites and brand assets must use HTTPS")
        return safe

@router.post("/match")
def match(body: MatchRequest, request: Request, user: User = Depends(get_current_user)):
    enforce_rate_limit(f"job-match:{request.client.host if request.client else 'unknown'}", limit=60, window_seconds=60)
    return score_job(body.title, body.description, body.skills)

@router.get("")
def list_opportunities(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(CandidateOpportunity).where(CandidateOpportunity.user_id == user.id)
                      .order_by(CandidateOpportunity.created_at.desc()).limit(500)).all()
    skills = db.scalars(select(CandidateSkill).where(CandidateSkill.user_id == user.id)).all()
    candidate_skills = [item.skill_name for item in skills]
    return [{"id": r.id, "title": r.title, "company": r.company, "location": r.location,
             "company_website": r.company_website, "company_domain": r.company_domain,
             "company_logo_url": r.company_logo_url, "company_favicon_url": r.company_favicon_url,
             "company_description": r.company_description, "company_brand_color": r.company_brand_color,
             "company_brand_source": r.company_brand_source,
             "source_name": r.source_name, "source_url": r.source_url, "status": r.status,
             "required_skills": r.required_skills, "salary_min": r.salary_min, "salary_max": r.salary_max,
             "employment_type": r.employment_type, "remote_type": r.remote_type,
             "posted_at": r.posted_at, "application_deadline": r.application_deadline,
             "fit": score_job(r.title, r.description + " " + " ".join(r.required_skills or []), candidate_skills),
             "created_at": r.created_at} for r in rows]

@router.post("", status_code=201)
def save_opportunity(body: OpportunityCreate, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    if body.source_url:
        existing = db.scalar(select(CandidateOpportunity).where(
            CandidateOpportunity.user_id == user.id,
            CandidateOpportunity.source_url == body.source_url))
        if existing:
            raise HTTPException(status_code=409, detail="This opportunity is already saved")
    row = CandidateOpportunity(user_id=user.id, **body.model_dump())
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="This opportunity URL is already saved") from exc
    db.refresh(row)
    skills = db.scalars(select(CandidateSkill).where(CandidateSkill.user_id == user.id)).all()
    fit = score_job(row.title, row.description + " " + " ".join(row.required_skills or []), [s.skill_name for s in skills])
    return {"id": row.id, "title": row.title, "company": row.company, "status": row.status, "fit": fit}

@router.post("/discover")
async def discover_jobs(body: DiscoveryRequest, user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    if not get_settings().job_discovery_enabled:
        raise HTTPException(status_code=503, detail="Job discovery is disabled. Enable JOB_DISCOVERY_ENABLED after reviewing your source settings.")
    enforce_rate_limit(f"job-discovery:{user.id}", limit=20, window_seconds=3600)
    try:
        discovered = (await discover_greenhouse(body.board, body.limit) if body.source == "greenhouse"
                      else await discover_lever(body.board, body.limit))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail="The selected job board returned an error") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Unable to reach the selected job board") from exc
    filtered = filter_jobs(discovered, keywords=body.keywords, location=body.location, remote_only=body.remote_only)
    profile = await discover_company_profile(body.source, body.board)
    if body.company_name and body.company_name.strip():
        profile["company"] = body.company_name.strip()
    saved, skipped, refreshed = 0, 0, 0
    results = []
    brand_fields = (
        "company_website", "company_domain", "company_logo_url",
        "company_favicon_url", "company_description", "company_brand_color", "company_brand_source",
    )
    fallback_name = body.board.replace("-", " ").title()
    for item in filtered:
        url = item.get("source_url", "")
        existing = db.scalar(select(CandidateOpportunity).where(
            CandidateOpportunity.user_id == user.id, CandidateOpportunity.source_url == url)) if url else None
        if not url:
            skipped += 1
            continue
        if existing:
            changed = False
            if existing.company in {"", fallback_name} and profile["company"] != fallback_name:
                existing.company = profile["company"]
                changed = True
            for key in brand_fields:
                if not getattr(existing, key) and profile.get(key):
                    setattr(existing, key, profile[key])
                    changed = True
            if changed:
                refreshed += 1
            skipped += 1
            continue
        item["company"] = profile["company"]
        item.update({key: profile.get(key, "") for key in (
            "company_website", "company_domain", "company_logo_url",
            "company_favicon_url", "company_description", "company_brand_color", "company_brand_source",
        )})
        row = CandidateOpportunity(user_id=user.id, **item)
        db.add(row)
        saved += 1
        results.append({"title": row.title, "company": row.company, "source_url": row.source_url,
                        "company_logo_url": row.company_logo_url, "company_website": row.company_website})
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A concurrent import saved one or more of these opportunities. Retry discovery to import remaining roles.") from exc
    return {"source": body.source, "board": body.board, "company_profile": {
                "name": profile["company"], "website": profile["company_website"],
                "domain": profile["company_domain"], "logo_url": profile["company_logo_url"],
                "favicon_url": profile["company_favicon_url"],
                "description": profile["company_description"],
                "brand_color": profile["company_brand_color"],
                "source_url": profile["company_brand_source"],
                "brand_assets_verified": bool(profile["company_logo_url"] or profile["company_favicon_url"]),
            }, "fetched": len(discovered), "matched_filters": len(filtered),
            "saved": saved, "refreshed_existing": refreshed,
            "duplicates_or_invalid": skipped, "items": results}
