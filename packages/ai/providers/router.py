from packages.ai.providers.registry import get_registry
from packages.ai.providers.base import GenerationRequest,GenerationResult
async def generate_with_fallback(request:GenerationRequest,preferred:str|None=None)->GenerationResult:
    from apps.api.app.core.config import get_settings
    settings=get_settings(); registry=get_registry()
    for name in [preferred or settings.ai_default_provider,settings.ai_fallback_provider,"mock"]:
        provider=registry.get(name)
        if provider:
            try: return await provider.generate(request)
            except Exception: continue
    raise RuntimeError("No configured AI provider could complete the request")
