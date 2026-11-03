import anthropic
from apps.api.app.core.config import get_settings
from packages.ai.providers.base import AIProvider,GenerationRequest,GenerationResult
class AnthropicProvider(AIProvider):
    name="anthropic"
    def __init__(self):
        s=get_settings()
        if not s.anthropic_api_key: raise RuntimeError("ANTHROPIC_API_KEY is missing")
        self.client=anthropic.AsyncAnthropic(api_key=s.anthropic_api_key); self.model=s.anthropic_default_model
    async def generate(self,request:GenerationRequest)->GenerationResult:
        r=await self.client.messages.create(model=request.model or self.model,system=request.system or "",messages=request.messages,max_tokens=request.max_tokens)
        text="\n".join(x.text for x in r.content if getattr(x,"type",None)=="text")
        return GenerationResult(text,r.model,{"input_tokens":r.usage.input_tokens,"output_tokens":r.usage.output_tokens})
    async def health_check(self): return True
