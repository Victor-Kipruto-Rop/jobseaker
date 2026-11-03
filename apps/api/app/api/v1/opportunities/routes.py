from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from apps.api.app.dependencies import get_current_user, get_db
from packages.ai.agents.job_matching.agent import score_job
from packages.database.models.identity import User
from packages.database.models.career import CandidateOpportunity, CandidateSkill

router = APIRouter()

class MatchRequest(BaseModel):
    title: str = Field(min_length=2, max_length=250)
    description: str = Field(min_length=20, max_length=20000)
    skills: list[str] = Field(default_factory=list, max_length=100)

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

@router.post("/match")
def match(body: MatchRequest):
    return score_job(body.title, body.description, body.skills)

@router.get("")
def list_opportunities(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(CandidateOpportunity).where(CandidateOpportunity.user_id == user.id)
                      .order_by(CandidateOpportunity.created_at.desc()).limit(500)).all()
    return [{"id": r.id, "title": r.title, "company": r.company, "location": r.location,
             "source_name": r.source_name, "source_url": r.source_url, "status": r.status,
             "required_skills": r.required_skills, "created_at": r.created_at} for r in rows]

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
    fit = score_job(row.title, row.description, [s.skill_name for s in skills])
    return {"id": row.id, "title": row.title, "company": row.company, "status": row.status, "fit": fit}
