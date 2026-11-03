import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from packages.ai.providers.registry import get_registry
from packages.ai.providers.base import GenerationRequest
from packages.ai.providers.router import generate_with_fallback
from packages.database.sessions import SessionLocal
from packages.database.models import AIUsage
from apps.api.app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    provider: str | None = Field(default=None, max_length=40)
    model: str | None = Field(default=None, max_length=120)
    system_instruction: str | None = Field(default=None, max_length=4000)
    max_tokens: int = Field(default=1200, ge=1, le=8000)


@router.get("/providers")
async def providers():
    registry = get_registry()
    settings = get_settings()
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
            "model": getattr(provider, "model", "mock-v1" if name == "mock" else "configured"),
        }
    return {
        "default_provider": settings.ai_default_provider,
        "fallback_provider": settings.ai_fallback_provider,
        "providers": result,
        "automation_paused": settings.global_automation_paused,
    }


@router.get("/usage")
def usage():
    """Return persisted token totals for the current installation."""
    with SessionLocal() as db:
        rows = db.execute(
            select(
                AIUsage.provider,
                AIUsage.model,
                func.coalesce(func.sum(AIUsage.input_tokens), 0),
                func.coalesce(func.sum(AIUsage.output_tokens), 0),
                func.count(AIUsage.id),
            ).group_by(AIUsage.provider, AIUsage.model)
        ).all()
    return {
        "scope": "installation",
        "pricing": "not_configured",
        "items": [
            {"provider": row[0], "model": row[1], "input_tokens": int(row[2]),
             "output_tokens": int(row[3]), "requests": int(row[4])}
            for row in rows
        ],
    }


@router.post("/chat")
async def chat(body: ChatRequest):
    registry = get_registry()
    settings = get_settings()
    requested = body.provider or settings.ai_default_provider
    if registry.get(requested) is None:
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
        actual_provider, generated = await generate_with_fallback(request, requested)
    except Exception as exc:
        logger.exception("AI generation failed", extra={"provider": requested})
        raise HTTPException(
            status_code=502,
            detail="AI generation failed. Check provider credentials, model access, and provider status.",
        ) from exc

    input_tokens = int(generated.usage.get("input_tokens", 0))
    output_tokens = int(generated.usage.get("output_tokens", 0))
    with SessionLocal() as db:
        db.add(AIUsage(
            provider=actual_provider,
            model=generated.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=0.0,
            created_at=datetime.now(timezone.utc),
        ))
        db.commit()

    return {
        "provider": actual_provider,
        "model": generated.model,
        "text": generated.text,
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
        "estimated_cost_usd": None,
        "cost_note": "Token usage is persisted. Monetary cost is intentionally unavailable until verified model pricing is configured.",
    }
