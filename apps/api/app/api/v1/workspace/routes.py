from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.dependencies import get_current_user, get_db
from packages.database.models.identity import User
from packages.database.models.career import CareerWorkspaceItem, AuditLog

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
    if values.get("title") is not None and not values["title"].strip():
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
