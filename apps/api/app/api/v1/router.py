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
