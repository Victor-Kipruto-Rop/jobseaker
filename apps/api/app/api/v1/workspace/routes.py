from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from apps.api.app.dependencies import get_current_user, get_db
from packages.database.models.identity import User
from packages.database.models.career import (
    CareerWorkspaceItem, AuditLog, Application, CandidateOpportunity, ResumeDocument,
    Company, Recruiter, GeneratedArtifact, CandidateSkill,
)

router = APIRouter()
ItemType = Literal["task", "note", "learning", "project", "contact"]
Statuses = {"task": {"open", "in_progress", "completed", "cancelled"},
            "note": {"open", "archived"},
            "learning": {"open", "in_progress", "completed", "paused"},
            "project": {"open", "in_progress", "completed", "paused", "archived"},
            "contact": {"open", "archived"}}
Priorities = {"low", "normal", "high", "urgent"}


class WorkspaceItemCreate(BaseModel):
    item_type: ItemType
    title: str = Field(min_length=1, max_length=250)
    description: str = Field(default="", max_length=20000)
    status: str = Field(default="open", max_length=30)
    priority: str = Field(default="normal", max_length=20)
    due_at: datetime | None = None
    metadata: dict = Field(default_factory=dict)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Title cannot be blank")
        return value.strip()

    @field_validator("metadata")
    @classmethod
    def metadata_size(cls, value: dict) -> dict:
        if len(str(value)) > 12000:
            raise ValueError("Metadata is too large")
        return value


class WorkspaceItemUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=250)
    description: str | None = Field(default=None, max_length=20000)
    status: str | None = Field(default=None, max_length=30)
    priority: str | None = Field(default=None, max_length=20)
    due_at: datetime | None = None
    metadata: dict | None = None


def serialize(row: CareerWorkspaceItem) -> dict:
    return {"id": row.id, "item_type": row.item_type, "title": row.title,
            "description": row.description, "status": row.status, "priority": row.priority,
            "due_at": row.due_at, "metadata": row.metadata_json or {},
            "created_at": row.created_at, "updated_at": row.updated_at}



@router.get("/search")
def search_workspace(q: str = Query(min_length=2, max_length=120),
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Escape SQL LIKE metacharacters so search input is treated as literal text.
    term = q.strip()
    if len(term) < 2:
        raise HTTPException(status_code=422, detail="Search query must contain at least two non-whitespace characters")
    term = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{term}%"
    opportunities = db.scalars(select(CandidateOpportunity).where(
        CandidateOpportunity.user_id == user.id,
        or_(CandidateOpportunity.title.ilike(pattern, escape="\\"),
            CandidateOpportunity.company.ilike(pattern, escape="\\"),
            CandidateOpportunity.location.ilike(pattern, escape="\\")),
    ).order_by(CandidateOpportunity.created_at.desc()).limit(8)).all()
    applications = db.scalars(select(Application).where(
        Application.user_id == user.id,
        or_(Application.role_title.ilike(pattern, escape="\\"),
            Application.company_name.ilike(pattern, escape="\\")),
    ).order_by(Application.created_at.desc()).limit(8)).all()
    items = db.scalars(select(CareerWorkspaceItem).where(
        CareerWorkspaceItem.user_id == user.id,
        or_(CareerWorkspaceItem.title.ilike(pattern, escape="\\"),
            CareerWorkspaceItem.description.ilike(pattern, escape="\\")),
    ).order_by(CareerWorkspaceItem.updated_at.desc()).limit(12)).all()
    resumes = db.scalars(select(ResumeDocument).where(
        ResumeDocument.user_id == user.id, ResumeDocument.filename.ilike(pattern, escape="\\")
    ).order_by(ResumeDocument.created_at.desc()).limit(5)).all()
    companies = db.scalars(select(Company).where(
        Company.user_id == user.id, Company.name.ilike(pattern, escape="\\")
    ).order_by(Company.name.asc()).limit(5)).all()
    recruiters = db.scalars(select(Recruiter).where(
        Recruiter.user_id == user.id,
        or_(Recruiter.full_name.ilike(pattern, escape="\\"), Recruiter.email.ilike(pattern, escape="\\")),
    ).order_by(Recruiter.full_name.asc()).limit(5)).all()
    artifacts = db.scalars(select(GeneratedArtifact).where(
        GeneratedArtifact.user_id == user.id, GeneratedArtifact.title.ilike(pattern, escape="\\")
    ).order_by(GeneratedArtifact.created_at.desc()).limit(5)).all()
    skills = db.scalars(select(CandidateSkill).where(
        CandidateSkill.user_id == user.id, CandidateSkill.skill_name.ilike(pattern, escape="\\")
    ).order_by(CandidateSkill.skill_name.asc()).limit(5)).all()
    routes = {"task": "/tasks", "note": "/notes", "learning": "/learning",
              "project": "/projects", "contact": "/contacts"}
    results = []
    results.extend({"id": row.id, "title": row.title, "subtitle": row.company or row.location or "Saved opportunity",
                    "href": "/saved-opportunities", "kind": "OPPORTUNITY"} for row in opportunities)
    results.extend({"id": row.id, "title": row.role_title, "subtitle": (row.company_name or "Application") + " · " + row.status,
                    "href": "/applications", "kind": "APPLICATION"} for row in applications)
    results.extend({"id": row.id, "title": row.title, "subtitle": row.item_type.replace("_", " "),
                    "href": routes.get(row.item_type, "/dashboard"), "kind": row.item_type.upper()} for row in items)
    results.extend({"id": row.id, "title": row.filename, "subtitle": "CV document",
                    "href": "/profile#resumes", "kind": "CV"} for row in resumes)
    results.extend({"id": row.id, "title": row.name, "subtitle": row.website or "Company record",
                    "href": "/contacts", "kind": "COMPANY"} for row in companies)
    results.extend({"id": row.id, "title": row.full_name, "subtitle": row.email or "Recruiter contact",
                    "href": "/contacts", "kind": "RECRUITER"} for row in recruiters)
    results.extend({"id": row.id, "title": row.title, "subtitle": row.artifact_type.replace("_", " "),
                    "href": "/profile#career-tools", "kind": "CAREER DRAFT"} for row in artifacts)
    results.extend({"id": row.id, "title": row.skill_name, "subtitle": row.proficiency.replace("_", " "),
                    "href": "/profile#skills", "kind": "SKILL"} for row in skills)
    return results[:20]


@router.get("")
def list_items(item_type: ItemType | None = Query(default=None), status: str | None = None,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    statement = select(CareerWorkspaceItem).where(CareerWorkspaceItem.user_id == user.id)
    if item_type:
        statement = statement.where(CareerWorkspaceItem.item_type == item_type)
    if status:
        statement = statement.where(CareerWorkspaceItem.status == status)
    rows = db.scalars(statement.order_by(CareerWorkspaceItem.due_at.asc().nullslast(),
                                         CareerWorkspaceItem.updated_at.desc()).limit(500)).all()
    return [serialize(row) for row in rows]


@router.post("", status_code=201)
def create_item(body: WorkspaceItemCreate, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    if body.status not in Statuses[body.item_type]:
        raise HTTPException(status_code=422, detail="Unsupported status for this item type")
    if body.priority not in Priorities:
        raise HTTPException(status_code=422, detail="Unsupported priority")
    row = CareerWorkspaceItem(user_id=user.id, item_type=body.item_type,
        title=body.title.strip(), description=body.description, status=body.status,
        priority=body.priority, due_at=body.due_at, metadata_json=body.metadata)
    db.add(row)
    db.flush()
    db.add(AuditLog(user_id=user.id, action="career_workspace.created", resource_type=row.item_type, resource_id=str(row.id)))
    db.commit()
    db.refresh(row)
    return serialize(row)


@router.patch("/{item_id}")
def update_item(item_id: int, body: WorkspaceItemUpdate,
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(CareerWorkspaceItem).where(
        CareerWorkspaceItem.id == item_id, CareerWorkspaceItem.user_id == user.id))
    if not row:
        raise HTTPException(status_code=404, detail="Workspace item not found")
    values = body.model_dump(exclude_unset=True)
    if values.get("title") is not None:
        values["title"] = values["title"].strip()
        if not values["title"]:
            raise HTTPException(status_code=422, detail="Title cannot be blank")
    if values.get("status") is not None and values["status"] not in Statuses[row.item_type]:
        raise HTTPException(status_code=422, detail="Unsupported status for this item type")
    if values.get("priority") is not None and values["priority"] not in Priorities:
        raise HTTPException(status_code=422, detail="Unsupported priority")
    if values.get("metadata") is not None and len(str(values["metadata"])) > 12000:
        raise HTTPException(status_code=422, detail="Metadata is too large")
    for key, value in values.items():
        if value is not None or key == "due_at":
            setattr(row, "metadata_json" if key == "metadata" else key,
                    value if key != "metadata" else value)
    db.add(AuditLog(user_id=user.id, action="career_workspace.updated", resource_type=row.item_type, resource_id=str(row.id)))
    db.commit()
    db.refresh(row)
    return serialize(row)


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: int, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    row = db.scalar(select(CareerWorkspaceItem).where(
        CareerWorkspaceItem.id == item_id, CareerWorkspaceItem.user_id == user.id))
    if not row:
        raise HTTPException(status_code=404, detail="Workspace item not found")
    db.add(AuditLog(user_id=user.id, action="career_workspace.deleted", resource_type=row.item_type, resource_id=str(row.id)))
    db.delete(row)
    db.commit()
    return None
