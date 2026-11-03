from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from apps.api.app.dependencies import get_current_user, get_db
from packages.database.models.identity import User
from packages.database.models.career import Application, Interview

router=APIRouter()
class InterviewInput(BaseModel):
    application_id:int|None=None
    scheduled_at:datetime|None=None
    interview_type:str=Field(default="unspecified",max_length=60)
    notes:str=Field(default="",max_length=10000)
    feedback:str=Field(default="",max_length=10000)

@router.get("")
def list_interviews(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(Interview).where(Interview.user_id==user.id)
                    .order_by(Interview.scheduled_at.desc().nullslast()).limit(200)).all()
    return [{"id":x.id,"application_id":x.application_id,"scheduled_at":x.scheduled_at,
             "interview_type":x.interview_type,"notes":x.notes,"feedback":x.feedback} for x in rows]

@router.post("",status_code=201)
def create_interview(body:InterviewInput,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    values=body.model_dump()
    if values["application_id"] is not None:
        application=db.scalar(select(Application).where(
            Application.id==values["application_id"],Application.user_id==user.id))
        if not application: raise HTTPException(status_code=404,detail="Application not found")
    row=Interview(user_id=user.id,**values)
    db.add(row);db.commit();db.refresh(row)
    return {"id":row.id,"scheduled_at":row.scheduled_at}
