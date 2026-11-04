from typing import Any

from sqlalchemy.orm import Session

from packages.automation.approvals.service import create_approval


def require_approval(
    db: Session,
    user_id: int,
    action_type: str,
    payload: dict[str, Any],
    rationale: str,
) -> dict[str, Any]:
    """Create a pending approval tied to the requesting account and transaction."""
    return create_approval(db, user_id, action_type, payload, rationale)
