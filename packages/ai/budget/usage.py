from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from packages.database.models.entities import AIUsage, AIUsageReservation
from packages.database.models.career import UserAIBudget, Notification

class AIQuotaExceeded(Exception):
    """Raised when an account has insufficient reserved monthly token capacity."""

def reserve_ai_tokens(db: Session, user_id: int, estimated_tokens: int,
                      ttl_seconds: int = 300) -> int | None:
    """Atomically reserve estimated tokens, then commit to release DB locks during inference."""
    budget = db.scalar(select(UserAIBudget).where(
        UserAIBudget.user_id == user_id).with_for_update())
    if not budget or not budget.hard_token_limit_enabled or budget.monthly_token_limit <= 0:
        db.rollback()
        return None

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    used = db.scalar(select(func.coalesce(func.sum(AIUsage.input_tokens + AIUsage.output_tokens), 0))
                     .where(AIUsage.user_id == user_id, AIUsage.created_at >= month_start)) or 0
    reserved = db.scalar(select(func.coalesce(func.sum(AIUsageReservation.reserved_tokens), 0))
                         .where(AIUsageReservation.user_id == user_id,
                                AIUsageReservation.status == "reserved",
                                AIUsageReservation.created_at >= month_start,
                                AIUsageReservation.expires_at > now)) or 0
    estimate = max(1, int(estimated_tokens))
    if int(used) + int(reserved) + estimate > budget.monthly_token_limit:
        db.rollback()
        raise AIQuotaExceeded("Your monthly AI token limit has been reached or reserved")

    row = AIUsageReservation(
        request_id=uuid4().hex, user_id=user_id, reserved_tokens=estimate,
        status="reserved", created_at=now,
        expires_at=now + timedelta(seconds=max(60, ttl_seconds)),
    )
    db.add(row)
    db.flush()
    reservation_id = row.id
    db.commit()
    return reservation_id

def finish_ai_reservation(db: Session, user_id: int, reservation_id: int | None,
                          status: str) -> None:
    if reservation_id is None:
        return
    if status not in {"completed", "failed"}:
        raise ValueError("Invalid AI reservation terminal status")
    row = db.scalar(select(AIUsageReservation).where(
        AIUsageReservation.id == reservation_id,
        AIUsageReservation.user_id == user_id,
    ).with_for_update())
    if row and row.status == "reserved":
        row.status = status
        row.completed_at = datetime.now(timezone.utc)

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

    budget = db.scalar(select(UserAIBudget).where(
        UserAIBudget.user_id == user_id).with_for_update())
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
