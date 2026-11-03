from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from apps.api.app.dependencies import get_current_user, get_db
from packages.database.models.identity import User
from packages.database.models.career import Notification

router=APIRouter()
@router.get("")
def list_notifications(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(Notification).where(Notification.user_id==user.id)
                    .order_by(Notification.created_at.desc()).limit(100)).all()
    return [{"id":x.id,"title":x.title,"body":x.body,"read_at":x.read_at,
             "created_at":x.created_at} for x in rows]

@router.post("/{notification_id}/read")
def mark_read(notification_id:int,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    row=db.scalar(select(Notification).where(Notification.id==notification_id,Notification.user_id==user.id))
    if not row: raise HTTPException(status_code=404,detail="Notification not found")
    row.read_at=datetime.now(timezone.utc)
    db.commit()
    return {"id":row.id,"read":True}
