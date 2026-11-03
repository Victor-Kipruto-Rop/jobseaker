from packages.ai.providers.base import AIProvider,GenerationRequest,GenerationResult
class MockProvider(AIProvider):
    name="mock"
    async def generate(self,request:GenerationRequest)->GenerationResult:
        prompt=request.messages[-1]["content"] if request.messages else ""
        return GenerationResult(f"[Mock AI] Request received: {prompt}","mock-v1")
    async def health_check(self): return True
