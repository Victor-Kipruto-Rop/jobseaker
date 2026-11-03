from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from apps.api.app.dependencies import get_current_user, get_db
from packages.database.models.identity import User
from packages.automation.approvals.service import create_approval, list_approvals, decide_approval

router = APIRouter()

class ApprovalRequest(BaseModel):
    action_type: str = Field(min_length=2, max_length=80)
    payload: dict
    rationale: str = Field(min_length=3, max_length=2000)

class ApprovalDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str = Field(default="", max_length=2000)

@router.get("/approvals")
def approvals(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list_approvals(db, user.id)

@router.post("/approvals", status_code=201)
def request_approval(body: ApprovalRequest, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    return create_approval(db, user.id, body.action_type, body.payload, body.rationale)

@router.post("/approvals/{approval_id}/decision")
def approval_decision(approval_id: int, body: ApprovalDecision,
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        result = decide_approval(db, user.id, approval_id, body.decision, body.note)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not result:
        raise HTTPException(status_code=404, detail="Approval not found")
    return result
