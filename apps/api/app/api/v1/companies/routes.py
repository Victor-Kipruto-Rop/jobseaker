from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from apps.api.app.dependencies import get_current_user, get_db
from packages.database.models.identity import User
from packages.database.models.career import Company
from packages.integrations.url_validation import validate_http_url

router=APIRouter()
class CompanyInput(BaseModel):
    name:str=Field(min_length=2,max_length=250)
    website:str=Field(default="",max_length=1000)
    careers_url:str=Field(default="",max_length=1000)
    description:str=Field(default="",max_length=10000)
    evidence:dict=Field(default_factory=dict)

    @field_validator("website", "careers_url")
    @classmethod
    def safe_urls(cls, value):
        return validate_http_url(value)

@router.get("")
def list_companies(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(Company).where(Company.user_id==user.id).order_by(Company.name)).all()
    return [{"id":x.id,"name":x.name,"website":x.website,"careers_url":x.careers_url,
             "description":x.description,"evidence":x.evidence} for x in rows]

@router.post("",status_code=201)
def create_company(body:CompanyInput,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    row=Company(user_id=user.id,**body.model_dump())
    db.add(row);db.commit();db.refresh(row)
    return {"id":row.id,"name":row.name}
