from packages.database.sessions import SessionLocal
from packages.database.models.entities import Approval
def create_approval(action_type,payload,rationale):
    db=SessionLocal()
    try:
        row=Approval(action_type=action_type,payload=payload,rationale=rationale,status="pending")
        db.add(row); db.commit(); db.refresh(row)
        return {"id":row.id,"action_type":row.action_type,"status":row.status}
    finally: db.close()
def list_approvals():
    db=SessionLocal()
    try:
        return [{"id":x.id,"action_type":x.action_type,"payload":x.payload,"rationale":x.rationale,"status":x.status,"created_at":x.created_at.isoformat()} for x in db.query(Approval).order_by(Approval.id.desc()).limit(100).all()]
    finally: db.close()
