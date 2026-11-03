from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, EmailStr, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from apps.api.app.dependencies import get_current_user, get_db
from packages.database.models.identity import User
from packages.database.models.career import Company, Recruiter
from packages.integrations.url_validation import validate_http_url

router=APIRouter()
class RecruiterInput(BaseModel):
    full_name:str=Field(min_length=2,max_length=200)
    email:EmailStr|None=None
    profile_url:str=Field(default="",max_length=1000)
    company_id:int|None=None
    notes:str=Field(default="",max_length=5000)

    @field_validator("profile_url")
    @classmethod
    def safe_profile_url(cls, value):
        return validate_http_url(value)

@router.get("")
def list_recruiters(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(Recruiter).where(Recruiter.user_id==user.id).order_by(Recruiter.full_name)).all()
    return [{"id":x.id,"full_name":x.full_name,"email":x.email,"profile_url":x.profile_url,
             "company_id":x.company_id,"notes":x.notes} for x in rows]

@router.post("",status_code=201)
def create_recruiter(body:RecruiterInput,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    values=body.model_dump()
    if values["company_id"] is not None:
        company=db.scalar(select(Company).where(Company.id==values["company_id"],Company.user_id==user.id))
        if not company: raise HTTPException(status_code=404,detail="Company not found")
    values["email"]=str(values["email"] or "")
    row=Recruiter(user_id=user.id,**values)
    db.add(row);db.commit();db.refresh(row)
    return {"id":row.id,"full_name":row.full_name}
