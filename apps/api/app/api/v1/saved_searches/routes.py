from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Literal
import re
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from apps.api.app.dependencies import get_current_user, get_db
from packages.database.models.identity import User
from packages.database.models.career import SavedSearch

router = APIRouter()
class SavedSearchInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    source: Literal["greenhouse", "lever"]
    board: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9-]{0,79}$")
    company_name: str | None = Field(default=None, max_length=250)

@router.get("")
def list_saved_searches(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(SavedSearch).where(SavedSearch.user_id == user.id)
                      .order_by(SavedSearch.created_at.desc())).all()
    return [{"id": row.id, "name": row.name, "query": row.query,
             "created_at": row.created_at} for row in rows]

@router.post("", status_code=201)
def create_saved_search(body: SavedSearchInput, user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    board = body.board.strip().lower()
    if not board.replace("-", "").isalnum():
        raise HTTPException(status_code=422, detail="Invalid job board identifier")
    row = SavedSearch(user_id=user.id, name=body.name,
        query={"source": body.source, "board": board, "company_name": body.company_name})
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "name": row.name, "query": row.query}

@router.delete("/{search_id}", status_code=204)
def delete_saved_search(search_id: int, user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    row = db.scalar(select(SavedSearch).where(SavedSearch.id == search_id, SavedSearch.user_id == user.id))
    if not row:
        raise HTTPException(status_code=404, detail="Saved search not found")
    db.delete(row)
    db.commit()
