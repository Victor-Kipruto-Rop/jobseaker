from fastapi import APIRouter
from pydantic import BaseModel,Field
from packages.ai.agents.job_matching.agent import score_job
router=APIRouter()
class MatchRequest(BaseModel):
    title:str=Field(min_length=2,max_length=250)
    description:str=Field(min_length=20,max_length=20000)
    skills:list[str]=Field(default_factory=list,max_length=100)
@router.post("/match")
def match(body:MatchRequest): return score_job(body.title,body.description,body.skills)
