from fastapi import APIRouter, Depends
from apps.api.app.dependencies import require_roles
from apps.api.app.api.v1.ai.routes import router as ai
from apps.api.app.api.v1.opportunities.routes import router as opportunities
from apps.api.app.api.v1.automations.routes import router as automations
from apps.api.app.api.v1.auth.routes import router as auth
router = APIRouter()
router.include_router(auth, prefix="/auth", tags=["authentication"])
router.include_router(ai, prefix="/ai", tags=["AI"], dependencies=[Depends(require_roles("candidate"))])
router.include_router(opportunities, prefix="/opportunities", tags=["opportunities"], dependencies=[Depends(require_roles("candidate"))])
router.include_router(automations, prefix="/automations", tags=["automation"], dependencies=[Depends(require_roles("candidate"))])
from apps.api.app.api.v1.profile.routes import router as profile
from apps.api.app.api.v1.applications.routes import router as applications
router.include_router(profile, prefix="/profile", tags=["candidate profile"], dependencies=[Depends(require_roles("candidate"))])
router.include_router(applications, prefix="/applications", tags=["applications"], dependencies=[Depends(require_roles("candidate"))])
from apps.api.app.api.v1.resumes.routes import router as resumes
router.include_router(resumes, prefix="/resumes", tags=["resumes and CV intelligence"], dependencies=[Depends(require_roles("candidate"))])
from apps.api.app.api.v1.companies.routes import router as companies
from apps.api.app.api.v1.recruiters.routes import router as recruiters
from apps.api.app.api.v1.interviews.routes import router as interviews
from apps.api.app.api.v1.analytics.routes import router as analytics
router.include_router(companies, prefix="/companies", tags=["companies"], dependencies=[Depends(require_roles("candidate"))])
router.include_router(recruiters, prefix="/recruiters", tags=["recruiters"], dependencies=[Depends(require_roles("candidate"))])
router.include_router(interviews, prefix="/interviews", tags=["interviews"], dependencies=[Depends(require_roles("candidate"))])
router.include_router(analytics, prefix="/analytics", tags=["career analytics"], dependencies=[Depends(require_roles("candidate"))])
from apps.api.app.api.v1.saved_searches.routes import router as saved_searches
router.include_router(saved_searches, prefix="/saved-searches", tags=["saved searches"], dependencies=[Depends(require_roles("candidate"))])
from apps.api.app.api.v1.notifications.routes import router as notifications
router.include_router(notifications, prefix="/notifications", tags=["notifications"], dependencies=[Depends(require_roles("candidate"))])
from apps.api.app.api.v1.integrations.gmail_routes import router as gmail, oauth_callback_router
router.include_router(gmail, prefix="/integrations", tags=["integrations"], dependencies=[Depends(require_roles("candidate"))])
# OAuth callbacks are authorized by their short-lived, single-use state bound to the initiating user.
router.include_router(oauth_callback_router, prefix="/integrations", tags=["integrations"])
from apps.api.app.api.v1.career_tools.routes import router as career_tools
router.include_router(career_tools, prefix="/career-tools", tags=["career intelligence"], dependencies=[Depends(require_roles("candidate"))])
