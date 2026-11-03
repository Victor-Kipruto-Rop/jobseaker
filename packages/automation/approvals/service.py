from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from packages.database.models.entities import Approval
from packages.database.models.career import AuditLog

def create_approval(db: Session, user_id: int, action_type: str, payload: dict, rationale: str):
    row = Approval(user_id=user_id, action_type=action_type, payload=payload,
                   rationale=rationale, status="pending")
    db.add(row)
    db.flush()
    db.add(AuditLog(user_id=user_id, action="approval.requested",
                    resource_type=action_type, resource_id=str(row.id)))
    db.commit()
    db.refresh(row)
    return {"id": row.id, "action_type": row.action_type, "status": row.status}

def list_approvals(db: Session, user_id: int):
    rows = db.scalars(select(Approval).where(Approval.user_id == user_id)
                      .order_by(Approval.id.desc()).limit(100)).all()
    return [{"id": row.id, "action_type": row.action_type, "payload": row.payload,
             "rationale": row.rationale, "status": row.status,
             "created_at": row.created_at.isoformat(), "decision_note": row.decision_note,
             "decided_at": row.decided_at.isoformat() if row.decided_at else None} for row in rows]

def decide_approval(db: Session, user_id: int, approval_id: int, decision: str, note: str = ""):
    if decision not in {"approved", "rejected"}:
        raise ValueError("Decision must be approved or rejected")
    row = db.scalar(select(Approval).where(
        Approval.id == approval_id, Approval.user_id == user_id).with_for_update())
    if not row:
        return None
    if row.status != "pending":
        raise ValueError("Only pending approvals can be decided")
    row.status = decision
    row.decision_note = note
    row.decided_at = datetime.now(timezone.utc)
    db.add(AuditLog(user_id=user_id, action="approval." + decision,
                    resource_type=row.action_type, resource_id=str(row.id)))
    db.commit()
    return {"id": row.id, "status": row.status, "decision_note": row.decision_note,
            "decided_at": row.decided_at.isoformat()}
