from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from typing import Literal
import httpx
from apps.api.app.core.redis_limits import enforce_rate_limit
from packages.integrations.job_boards.connectors import discover_greenhouse, discover_lever
from packages.integrations.url_validation import validate_http_url
from sqlalchemy import select
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

class OpportunityCreate(BaseModel):
    title: str = Field(min_length=2, max_length=250)
    company: str = Field(default="", max_length=250)
    description: str = Field(default="", max_length=30000)
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

@router.post("/match")
def match(body: MatchRequest, request: Request):
    enforce_rate_limit(f"job-match:{request.client.host if request.client else 'unknown'}", limit=60, window_seconds=60)
    return score_job(body.title, body.description, body.skills)

@router.get("")
def list_opportunities(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(CandidateOpportunity).where(CandidateOpportunity.user_id == user.id)
                      .order_by(CandidateOpportunity.created_at.desc()).limit(500)).all()
    skills = db.scalars(select(CandidateSkill).where(CandidateSkill.user_id == user.id)).all()
    candidate_skills = [item.skill_name for item in skills]
    return [{"id": r.id, "title": r.title, "company": r.company, "location": r.location,
             "source_name": r.source_name, "source_url": r.source_url, "status": r.status,
             "required_skills": r.required_skills, "fit": score_job(r.title, r.description + " " + " ".join(r.required_skills or []), candidate_skills),
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
    db.commit()
    db.refresh(row)
    skills = db.scalars(select(CandidateSkill).where(CandidateSkill.user_id == user.id)).all()
    fit = score_job(row.title, row.description + " " + " ".join(row.required_skills or []), [s.skill_name for s in skills])
    return {"id": row.id, "title": row.title, "company": row.company, "status": row.status, "fit": fit}

@router.post("/discover")
async def discover_jobs(body: DiscoveryRequest, user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    enforce_rate_limit(f"job-discovery:{user.id}", limit=20, window_seconds=3600)
    try:
        discovered = (await discover_greenhouse(body.board, body.limit) if body.source == "greenhouse"
                      else await discover_lever(body.board, body.limit))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail="The selected job board returned an error") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Unable to reach the selected job board") from exc
    saved, skipped = 0, 0
    results = []
    for item in discovered:
        url = item.get("source_url", "")
        if not url or db.scalar(select(CandidateOpportunity.id).where(
            CandidateOpportunity.user_id == user.id, CandidateOpportunity.source_url == url)):
            skipped += 1
            continue
        if body.company_name:
            item["company"] = body.company_name
        row = CandidateOpportunity(user_id=user.id, **item)
        db.add(row)
        saved += 1
        results.append({"title": row.title, "company": row.company, "source_url": row.source_url})
    db.commit()
    return {"source": body.source, "board": body.board, "fetched": len(discovered),
            "saved": saved, "duplicates_or_invalid": skipped, "items": results}
