from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from packages.ai.providers.registry import get_registry
from packages.ai.providers.base import GenerationRequest
router=APIRouter()
class ChatRequest(BaseModel):
    message:str=Field(min_length=1,max_length=12000)
    provider:str|None=None
    system_instruction:str|None=Field(default=None,max_length=4000)
@router.get("/providers")
def providers(): return get_registry().status()
@router.post("/chat")
async def chat(body:ChatRequest):
    provider=get_registry().get(body.provider)
    if not provider: raise HTTPException(400,"Provider is not enabled or configured")
    result=await provider.generate(GenerationRequest(messages=[{"role":"user","content":body.message}],system=body.system_instruction or "You are JobSeeker's career intelligence assistant. Never invent candidate facts."))
    return {"provider":provider.name,"model":result.model,"text":result.text,"usage":result.usage,"estimated_cost_usd":result.estimated_cost_usd}
