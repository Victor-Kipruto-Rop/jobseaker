from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from apps.api.app.dependencies import get_current_user, get_db
from packages.database.models.identity import User
from packages.database.models.career import Application, CandidateOpportunity, Interview
from packages.database.models.entities import AIUsage

router=APIRouter()
@router.get("/overview")
def overview(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    app_counts=dict(db.execute(select(Application.status,func.count(Application.id))
        .where(Application.user_id==user.id).group_by(Application.status)).all())
    jobs=db.scalar(select(func.count(CandidateOpportunity.id)).where(CandidateOpportunity.user_id==user.id)) or 0
    interviews=db.scalar(select(func.count(Interview.id)).where(Interview.user_id==user.id)) or 0
    usage=db.scalar(select(func.coalesce(func.sum(AIUsage.input_tokens+AIUsage.output_tokens),0))
        .where(AIUsage.user_id==user.id)) or 0
    return {"saved_opportunities":int(jobs),"applications":sum(app_counts.values()),
            "applications_by_status":app_counts,"interviews":int(interviews),"ai_tokens":int(usage)}
