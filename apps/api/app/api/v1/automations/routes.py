from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from apps.api.app.dependencies import get_current_user
from packages.database.models.identity import User
from packages.automation.approvals.service import create_approval, list_approvals
router = APIRouter()

class ApprovalRequest(BaseModel):
    action_type: str = Field(min_length=2, max_length=80)
    payload: dict
    rationale: str = Field(min_length=3, max_length=2000)

@router.get("/approvals")
def approvals(user: User = Depends(get_current_user)):
    return list_approvals(user.id)

@router.post("/approvals")
def request_approval(body: ApprovalRequest, user: User = Depends(get_current_user)):
    return create_approval(user.id, body.action_type, body.payload, body.rationale)
