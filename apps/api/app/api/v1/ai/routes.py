import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from packages.ai.providers.registry import get_registry
from packages.ai.providers.base import GenerationRequest

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    provider: str | None = None
    model: str | None = Field(default=None, max_length=120)
    system_instruction: str | None = Field(default=None, max_length=4000)
    max_tokens: int = Field(default=1200, ge=1, le=8000)


@router.get("/providers")
async def providers():
    """Return configured providers and a lightweight adapter health result."""
    registry = get_registry()
    settings = __import__("apps.api.app.core.config", fromlist=["get_settings"]).get_settings()
    result = {}
    for name, provider in registry.providers.items():
        try:
            healthy = await provider.health_check()
        except Exception:
            logger.exception("AI provider health check failed", extra={"provider": name})
            healthy = False
        result[name] = {
            "configured": True,
            "enabled": True,
            "healthy": bool(healthy),
            "default": name == settings.ai_default_provider,
            "model": getattr(provider, "model", "mock"),
        }
    return {
        "default_provider": settings.ai_default_provider,
        "fallback_provider": settings.ai_fallback_provider,
        "providers": result,
        "automation_paused": settings.global_automation_paused,
    }


@router.post("/chat")
async def chat(body: ChatRequest):
    registry = get_registry()
    provider = registry.get(body.provider)
    if provider is None:
        raise HTTPException(status_code=400, detail="Provider is not enabled or configured")
    request = GenerationRequest(
        messages=[{"role": "user", "content": body.message}],
        system=body.system_instruction or (
            "You are JobSeeker's career intelligence assistant. "
            "Never invent candidate facts, employment history, qualifications, or application outcomes. "
            "Clearly label assumptions and produce drafts for human review."
        ),
        model=body.model,
        max_tokens=body.max_tokens,
    )
    try:
        generated = await provider.generate(request)
    except Exception as exc:
        logger.exception("AI generation failed", extra={"provider": provider.name})
        raise HTTPException(
            status_code=502,
            detail=f"The selected AI provider failed. Check its API key, model access, and provider status.",
        ) from exc
    return {
        "provider": provider.name,
        "model": generated.model,
        "text": generated.text,
        "usage": generated.usage,
        "estimated_cost_usd": generated.estimated_cost_usd,
        "cost_note": "Cost is reported only when the provider adapter supplies a verified estimate.",
    }
