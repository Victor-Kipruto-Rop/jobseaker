from fastapi import APIRouter
from apps.api.app.api.v1.ai.routes import router as ai
from apps.api.app.api.v1.opportunities.routes import router as opportunities
from apps.api.app.api.v1.automations.routes import router as automations
router=APIRouter()
router.include_router(ai,prefix="/ai",tags=["AI"])
router.include_router(opportunities,prefix="/opportunities",tags=["opportunities"])
router.include_router(automations,prefix="/automations",tags=["automation"])
