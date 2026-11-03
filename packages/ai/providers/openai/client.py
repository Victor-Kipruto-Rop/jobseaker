from openai import AsyncOpenAI
from apps.api.app.core.config import get_settings
from packages.ai.providers.base import AIProvider,GenerationRequest,GenerationResult
class OpenAIProvider(AIProvider):
    name="openai"
    def __init__(self):
        s=get_settings()
        if not s.openai_api_key: raise RuntimeError("OPENAI_API_KEY is missing")
        self.client=AsyncOpenAI(api_key=s.openai_api_key); self.model=s.openai_default_model
    async def generate(self,request:GenerationRequest)->GenerationResult:
        r=await self.client.responses.create(model=request.model or self.model,instructions=request.system or "",input=request.messages,max_output_tokens=request.max_tokens)
        u=r.usage
        return GenerationResult(r.output_text,r.model,{"input_tokens":u.input_tokens if u else 0,"output_tokens":u.output_tokens if u else 0})
    async def health_check(self): return True
