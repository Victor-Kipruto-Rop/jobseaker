from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.app.dependencies import get_current_user, get_db
from packages.database.models.identity import User
from packages.database.models.career import CandidateOpportunity, Company
from packages.integrations.url_validation import validate_http_url

router = APIRouter()


class CompanyInput(BaseModel):
    name: str = Field(min_length=2, max_length=250)
    website: str = Field(default="", max_length=1000)
    careers_url: str = Field(default="", max_length=1000)
    description: str = Field(default="", max_length=10000)
    industry: str = Field(default="", max_length=160)
    headquarters: str = Field(default="", max_length=250)
    logo_url: str = Field(default="", max_length=2000)
    favicon_url: str = Field(default="", max_length=2000)
    brand_color: str = Field(default="", max_length=7, pattern=r"^$|^#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?$")
    social_links: dict = Field(default_factory=dict)
    evidence: dict = Field(default_factory=dict)

    @field_validator("website", "careers_url", "logo_url", "favicon_url")
    @classmethod
    def secure_urls(cls, value):
        safe = validate_http_url(value)
        if safe and not safe.lower().startswith("https://"):
            raise ValueError("Company websites and brand assets must use HTTPS")
        return safe

    @field_validator("social_links")
    @classmethod
    def validate_social_links(cls, value):
        if len(value) > 12:
            raise ValueError("Too many social profile links")
        cleaned = {}
        for key, url in value.items():
            if key not in {"linkedin", "x", "github", "facebook", "youtube", "instagram"}:
                continue
            safe = validate_http_url(str(url))
            if safe and safe.lower().startswith("https://"):
                cleaned[key] = safe
        return cleaned


def serialize_company(company: Company, opportunity_count: int = 0):
    return {
        "id": company.id,
        "name": company.name,
        "website": company.website,
        "domain": company.domain,
        "careers_url": company.careers_url,
        "description": company.description,
        "industry": company.industry,
        "headquarters": company.headquarters,
        "logo_url": company.logo_url,
        "favicon_url": company.favicon_url,
        "brand_color": company.brand_color,
        "source_provider": company.source_provider,
        "source_board": company.source_board,
        "source_url": company.source_url,
        "social_links": company.social_links or {},
        "evidence": company.evidence or {},
        "verified_at": company.verified_at,
        "last_enriched_at": company.last_enriched_at,
        "opportunity_count": opportunity_count,
    }


@router.get("")
def list_companies(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Company, func.count(CandidateOpportunity.id))
        .outerjoin(
            CandidateOpportunity,
            (CandidateOpportunity.company_id == Company.id)
            & (CandidateOpportunity.user_id == user.id),
        )
        .where(Company.user_id == user.id)
        .group_by(Company.id)
        .order_by(Company.name.asc())
        .limit(500)
    ).all()
    return [serialize_company(company, count) for company, count in rows]


@router.get("/{company_id}")
def get_company(company_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    company = db.scalar(select(Company).where(
        Company.id == company_id, Company.user_id == user.id,
    ))
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    opportunities = db.scalars(select(CandidateOpportunity).where(
        CandidateOpportunity.company_id == company.id,
        CandidateOpportunity.user_id == user.id,
    ).order_by(CandidateOpportunity.created_at.desc()).limit(100)).all()
    return {
        **serialize_company(company, len(opportunities)),
        "opportunities": [{
            "id": item.id,
            "title": item.title,
            "location": item.location,
            "employment_type": item.employment_type,
            "remote_type": item.remote_type,
            "source_name": item.source_name,
            "source_url": item.source_url,
            "status": item.status,
            "created_at": item.created_at,
        } for item in opportunities],
    }


@router.post("", status_code=201)
def create_company(body: CompanyInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = Company(user_id=user.id, **body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_company(row)
