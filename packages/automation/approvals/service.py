from sqlalchemy import select
from packages.database.sessions import SessionLocal
from packages.database.models.entities import Approval

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
                 "created_at": row.created_at.isoformat()} for row in rows]
