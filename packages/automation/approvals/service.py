from sqlalchemy import select
from packages.database.sessions import SessionLocal
from packages.database.models.entities import Approval
from packages.database.models.career import AuditLog
from datetime import datetime, timezone

def create_approval(user_id, action_type, payload, rationale):
    with SessionLocal() as db:
        row = Approval(user_id=user_id, action_type=action_type, payload=payload,
                       rationale=rationale, status="pending")
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"id": row.id, "action_type": row.action_type, "status": row.status}

def list_approvals(user_id):
    with SessionLocal() as db:
        rows = db.scalars(select(Approval).where(Approval.user_id == user_id)
                          .order_by(Approval.id.desc()).limit(100)).all()
        return [{"id": row.id, "action_type": row.action_type, "payload": row.payload,
                 "rationale": row.rationale, "status": row.status,
                 "created_at": row.created_at.isoformat(), "decision_note": row.decision_note,
                 "decided_at": row.decided_at.isoformat() if row.decided_at else None} for row in rows]

def decide_approval(user_id, approval_id, decision, note=""):
    if decision not in {"approved", "rejected"}:
        raise ValueError("Decision must be approved or rejected")
    with SessionLocal() as db:
        row = db.scalar(select(Approval).where(
            Approval.id == approval_id, Approval.user_id == user_id))
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
