from fastapi import APIRouter
from apps.api.app.api.v1.ai.routes import router as ai
from apps.api.app.api.v1.opportunities.routes import router as opportunities
from apps.api.app.api.v1.automations.routes import router as automations
from apps.api.app.api.v1.auth.routes import router as auth
router = APIRouter()
router.include_router(auth, prefix="/auth", tags=["authentication"])
router.include_router(ai, prefix="/ai", tags=["AI"])
router.include_router(opportunities, prefix="/opportunities", tags=["opportunities"])
router.include_router(automations, prefix="/automations", tags=["automation"])
from apps.api.app.api.v1.profile.routes import router as profile
from apps.api.app.api.v1.applications.routes import router as applications
router.include_router(profile, prefix="/profile", tags=["candidate profile"])
router.include_router(applications, prefix="/applications", tags=["applications"])
from apps.api.app.api.v1.resumes.routes import router as resumes
router.include_router(resumes, prefix="/resumes", tags=["resumes and CV intelligence"])
from apps.api.app.api.v1.companies.routes import router as companies
from apps.api.app.api.v1.recruiters.routes import router as recruiters
from apps.api.app.api.v1.interviews.routes import router as interviews
from apps.api.app.api.v1.analytics.routes import router as analytics
router.include_router(companies, prefix="/companies", tags=["companies"])
router.include_router(recruiters, prefix="/recruiters", tags=["recruiters"])
router.include_router(interviews, prefix="/interviews", tags=["interviews"])
router.include_router(analytics, prefix="/analytics", tags=["career analytics"])
from apps.api.app.api.v1.saved_searches.routes import router as saved_searches
router.include_router(saved_searches, prefix="/saved-searches", tags=["saved searches"])
from apps.api.app.api.v1.notifications.routes import router as notifications
router.include_router(notifications, prefix="/notifications", tags=["notifications"])
from apps.api.app.api.v1.integrations.gmail_routes import router as gmail
router.include_router(gmail, prefix="/integrations", tags=["integrations"])
