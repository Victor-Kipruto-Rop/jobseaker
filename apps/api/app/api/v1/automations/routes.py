from fastapi import APIRouter
from pydantic import BaseModel,Field
from packages.automation.approvals.service import create_approval,list_approvals
router=APIRouter()
class ApprovalRequest(BaseModel):
    action_type:str=Field(min_length=2,max_length=80)
    payload:dict
    rationale:str=Field(min_length=3,max_length=2000)
@router.get("/approvals")
def approvals(): return list_approvals()
@router.post("/approvals")
def request_approval(body:ApprovalRequest): return create_approval(body.action_type,body.payload,body.rationale)
