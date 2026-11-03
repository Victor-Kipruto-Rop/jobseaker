import asyncio
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from packages.ai.providers.registry import get_registry
from packages.ai.providers.base import GenerationRequest
from packages.ai.providers.router import generate_with_fallback
from packages.database.models import AIUsage
from packages.database.models.career import AIConversation, AIMessage, UserAIBudget
from apps.api.app.core.config import get_settings
from apps.api.app.dependencies import get_current_user, get_db
from packages.database.models.identity import User

logger = logging.getLogger(__name__)
router = APIRouter()

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    provider: str | None = Field(default=None, max_length=40)
    model: str | None = Field(default=None, max_length=120)
    system_instruction: str | None = Field(default=None, max_length=4000)
    max_tokens: int = Field(default=1200, ge=1, le=8000)
    conversation_id: int | None = None

@router.get("/providers")
async def providers(user: User = Depends(get_current_user)):
    registry = get_registry()
    settings = get_settings()
    result = {}
    for name, provider in registry.providers.items():
        try:
            credential_ok = await provider.health_check()
        except Exception:
            logger.exception("AI provider credential check failed", extra={"provider": name})
            credential_ok = False
        result[name] = {
            "configured": bool(credential_ok),
            "enabled": bool(credential_ok) or name == "mock",
            "credential_check": "passed" if credential_ok else "failed",
            "healthy": bool(credential_ok),
            "default": name == settings.ai_default_provider,
            "model": getattr(provider, "model", "mock-v1" if name == "mock" else "configured"),
        }
    return {"default_provider": settings.ai_default_provider, "fallback_provider": settings.ai_fallback_provider,
            "providers": result, "automation_paused": settings.global_automation_paused}

@router.get("/conversations")
def conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(AIConversation).where(AIConversation.user_id == user.id)
                      .order_by(AIConversation.updated_at.desc()).limit(100)).all()
    return [{"id": row.id, "title": row.title, "created_at": row.created_at,
             "updated_at": row.updated_at} for row in rows]

@router.get("/conversations/{conversation_id}/messages")
def conversation_messages(conversation_id: int, user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    conversation = db.scalar(select(AIConversation).where(
        AIConversation.id == conversation_id, AIConversation.user_id == user.id))
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    rows = db.scalars(select(AIMessage).where(
        AIMessage.conversation_id == conversation_id, AIMessage.user_id == user.id
    ).order_by(AIMessage.created_at.asc()).limit(500)).all()
    return [{"id": row.id, "role": row.role, "content": row.content,
             "provider": row.provider, "model": row.model, "created_at": row.created_at} for row in rows]

@router.get("/usage")
def usage(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(AIUsage.provider, AIUsage.model,
        func.coalesce(func.sum(AIUsage.input_tokens), 0),
        func.coalesce(func.sum(AIUsage.output_tokens), 0), func.count(AIUsage.id)
    ).where(AIUsage.user_id == user.id).group_by(AIUsage.provider, AIUsage.model)).all()
    return {"scope": "user", "pricing": "not_configured", "items": [
        {"provider": row[0], "model": row[1], "input_tokens": int(row[2]),
         "output_tokens": int(row[3]), "requests": int(row[4])} for row in rows]}

@router.post("/chat")
async def chat(body: ChatRequest, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    registry = get_registry()
    settings = get_settings()
    requested = body.provider or settings.ai_default_provider
    if registry.get(requested) is None:
        raise HTTPException(status_code=400, detail="Provider is not enabled or configured")
    now = datetime.now(timezone.utc)
    conversation = None
    if body.conversation_id is not None:
        conversation = db.scalar(select(AIConversation).where(
            AIConversation.id == body.conversation_id, AIConversation.user_id == user.id))
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = AIConversation(user_id=user.id, title=body.message[:80])
        db.add(conversation)
        db.flush()
    history = db.scalars(select(AIMessage).where(
        AIMessage.conversation_id == conversation.id, AIMessage.user_id == user.id
    ).order_by(AIMessage.created_at.desc()).limit(20)).all()
    messages = [{"role": item.role, "content": item.content} for item in reversed(history)]
    messages.append({"role": "user", "content": body.message})
    budget = db.scalar(select(UserAIBudget).where(UserAIBudget.user_id == user.id).with_for_update())
    if budget and budget.hard_token_limit_enabled and budget.monthly_token_limit > 0:
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        used = db.scalar(select(func.coalesce(func.sum(AIUsage.input_tokens + AIUsage.output_tokens), 0))
                         .where(AIUsage.user_id == user.id, AIUsage.created_at >= month_start)) or 0
        context_chars = sum(len(item["content"]) for item in messages)
        estimated_input_tokens = max(1, (context_chars + 3) // 4)
        if int(used) + estimated_input_tokens + body.max_tokens > budget.monthly_token_limit:
            raise HTTPException(status_code=429, detail="Your monthly AI token limit has been reached")
    request = GenerationRequest(
        messages=messages,
        system=body.system_instruction or (
            "You are JobSeeker's career intelligence assistant. Never invent candidate facts, "
            "employment history, qualifications, job details, or application outcomes. "
            "Distinguish verified evidence from assumptions. All external actions require approval."
        ),
        model=body.model, max_tokens=body.max_tokens,
    )
    try:
        actual_provider, generated = await asyncio.wait_for(
            generate_with_fallback(request, requested), timeout=95)
    except asyncio.TimeoutError as exc:
        db.rollback()
        raise HTTPException(status_code=504, detail="AI provider request timed out. Please retry.") from exc
    except Exception as exc:
        db.rollback()
        logger.exception("AI generation failed", extra={"provider": requested})
        raise HTTPException(status_code=502, detail="AI generation failed. Check provider credentials and model access.") from exc
    input_tokens = int(generated.usage.get("input_tokens", 0))
    output_tokens = int(generated.usage.get("output_tokens", 0))
    db.add(AIMessage(user_id=user.id, conversation_id=conversation.id, role="user", content=body.message))
    db.add(AIMessage(user_id=user.id, conversation_id=conversation.id, role="assistant",
                     content=generated.text, provider=actual_provider, model=generated.model))
    db.add(AIUsage(user_id=user.id, provider=actual_provider, model=generated.model,
                   input_tokens=input_tokens, output_tokens=output_tokens,
                   estimated_cost_usd=None, created_at=now))
    conversation.updated_at = now
    db.commit()
    return {"conversation_id": conversation.id, "provider": actual_provider, "model": generated.model,
            "text": generated.text, "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
            "estimated_cost_usd": None,
            "cost_note": "Token usage is persisted per user. Monetary cost remains unavailable until a verified, versioned pricing catalog is configured."}

class BudgetUpdate(BaseModel):
    monthly_token_limit: int = Field(default=0, ge=0, le=100000000)
    hard_token_limit_enabled: bool = False
    alert_threshold_percent: int = Field(default=80, ge=1, le=100)

def _budget_snapshot(user: User, db: Session, budget: UserAIBudget | None):
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    used = db.scalar(select(func.coalesce(func.sum(AIUsage.input_tokens + AIUsage.output_tokens), 0))
                     .where(AIUsage.user_id == user.id, AIUsage.created_at >= month_start)) or 0
    limit = budget.monthly_token_limit if budget else 0
    enabled = bool(budget and budget.hard_token_limit_enabled)
    remaining = max(0, limit - int(used)) if limit > 0 else None
    percentage = round(100 * int(used) / limit, 1) if limit > 0 else None
    return {
        "monthly_token_limit": limit,
        "hard_token_limit_enabled": enabled,
        "alert_threshold_percent": budget.alert_threshold_percent if budget else 80,
        "monthly_tokens_used": int(used),
        "remaining_tokens": remaining,
        "usage_percent": percentage,
        "enforcement": "token_limit" if enabled and limit > 0 else "disabled",
        "period_start": month_start.isoformat(),
    }

@router.get("/budget")
def get_budget(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    budget = db.scalar(select(UserAIBudget).where(UserAIBudget.user_id == user.id))
    return _budget_snapshot(user, db, budget)

@router.put("/budget")
def update_budget(body: BudgetUpdate, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    budget = db.scalar(select(UserAIBudget).where(UserAIBudget.user_id == user.id))
    if not budget:
        budget = UserAIBudget(user_id=user.id)
        db.add(budget)
    budget.monthly_token_limit = body.monthly_token_limit
    budget.hard_token_limit_enabled = body.hard_token_limit_enabled
    budget.alert_threshold_percent = body.alert_threshold_percent
    db.commit()
    return _budget_snapshot(user, db, budget)
