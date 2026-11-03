from datetime import datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from packages.database.models.entities import AIUsage
from packages.database.models.career import UserAIBudget, Notification

def record_ai_usage(db: Session, user_id: int, provider: str, model: str,
                    input_tokens: int, output_tokens: int,
                    created_at: datetime | None = None) -> AIUsage:
    """Persist usage and emit at most one threshold notification per user/month."""
    now = created_at or datetime.now(timezone.utc)
    usage = AIUsage(user_id=user_id, provider=provider, model=model,
                    input_tokens=max(0, int(input_tokens)),
                    output_tokens=max(0, int(output_tokens)),
                    estimated_cost_usd=None, created_at=now)
    db.add(usage)
    db.flush()

    budget = db.scalar(select(UserAIBudget).where(UserAIBudget.user_id == user_id))
    if not budget or budget.monthly_token_limit <= 0 or budget.alert_threshold_percent <= 0:
        return usage

    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = db.scalar(select(func.coalesce(func.sum(AIUsage.input_tokens + AIUsage.output_tokens), 0))
                      .where(AIUsage.user_id == user_id, AIUsage.created_at >= month_start)) or 0
    threshold = max(1, (budget.monthly_token_limit * budget.alert_threshold_percent + 99) // 100)
    marker = "ai-budget:" + month_start.strftime("%Y-%m")
    existing = db.scalar(select(Notification.id).where(
        Notification.user_id == user_id, Notification.body.like(marker + "%")))
    if int(total) >= threshold and not existing:
        db.add(Notification(
            user_id=user_id,
            title="AI token budget threshold reached",
            body=(marker + f" Month-to-date usage has reached {int(total):,} tokens "
                  f"against a configured allowance of {budget.monthly_token_limit:,}."),
        ))
    return usage
