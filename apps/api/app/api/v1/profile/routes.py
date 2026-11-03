from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from typing import Literal
from sqlalchemy import select
from sqlalchemy.orm import Session
from apps.api.app.dependencies import get_current_user, get_db
from packages.database.models.identity import User
from packages.database.models.career import CandidateProfile, CandidateSkill

router = APIRouter()

class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    headline: str | None = Field(default=None, max_length=250)
    summary: str | None = Field(default=None, max_length=8000)
    location: str | None = Field(default=None, max_length=250)
    target_roles: list[str] | None = Field(default=None, max_length=30)
    preferences: dict | None = None
    profile_data: dict | None = None

class SkillInput(BaseModel):
    skill_name: str = Field(min_length=1, max_length=120)
    proficiency: Literal["not_assessed", "beginner", "intermediate", "advanced", "expert"] = "not_assessed"
    evidence: str = Field(default="", max_length=2000)

    @field_validator("skill_name")
    @classmethod
    def clean_skill_name(cls, value):
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Skill name cannot be blank")
        return cleaned

@router.get("")
def get_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    skills = db.scalars(select(CandidateSkill).where(CandidateSkill.user_id == user.id)).all()
    return {"user": {"id": user.id, "email": user.email, "full_name": user.full_name},
            "profile": None if not profile else {"headline": profile.headline, "summary": profile.summary,
            "location": profile.location, "target_roles": profile.target_roles,
            "preferences": profile.preferences, "profile_data": profile.profile_data},
            "skills": [{"id": s.id, "skill_name": s.skill_name, "proficiency": s.proficiency,
                        "evidence": s.evidence} for s in skills]}

@router.patch("")
def update_profile(body: ProfileUpdate, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    values = body.model_dump(exclude_unset=True)
    full_name = values.pop("full_name", None)
    if full_name is not None:
        user.full_name = full_name
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    if not profile:
        profile = CandidateProfile(user_id=user.id)
        db.add(profile)
    for key, value in values.items():
        if value is not None:
            setattr(profile, key, value)
    db.commit()
    return {"status": "updated"}

@router.post("/skills", status_code=201)
def add_skill(body: SkillInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = db.scalar(select(CandidateSkill).where(
        CandidateSkill.user_id == user.id, CandidateSkill.skill_name.ilike(body.skill_name)))
    if existing:
        existing.proficiency, existing.evidence = body.proficiency, body.evidence
        db.commit()
        return {"id": existing.id, "status": "updated"}
    item = CandidateSkill(user_id=user.id, **body.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "status": "created"}

@router.delete("/skills/{skill_id}", status_code=204)
def delete_skill(skill_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.scalar(select(CandidateSkill).where(
        CandidateSkill.id == skill_id, CandidateSkill.user_id == user.id))
    if item:
        db.delete(item)
        db.commit()
