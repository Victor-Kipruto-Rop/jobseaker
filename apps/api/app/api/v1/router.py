from fastapi import APIRouter, Depends

from apps.api.app.dependencies import require_roles
from apps.api.app.api.v1.ai.routes import router as ai
from apps.api.app.api.v1.applications.routes import router as applications
from apps.api.app.api.v1.auth.routes import router as auth
from apps.api.app.api.v1.automations.routes import router as automations
from apps.api.app.api.v1.analytics.routes import router as analytics
from apps.api.app.api.v1.career_tools.routes import router as career_tools
from apps.api.app.api.v1.companies.routes import router as companies
from apps.api.app.api.v1.interviews.routes import router as interviews
from apps.api.app.api.v1.integrations.gmail_routes import (
    oauth_callback_router,
    router as gmail,
)
from apps.api.app.api.v1.notifications.routes import router as notifications
from apps.api.app.api.v1.opportunities.routes import router as opportunities
from apps.api.app.api.v1.profile.routes import router as profile
from apps.api.app.api.v1.recruiters.routes import router as recruiters
from apps.api.app.api.v1.resumes.routes import router as resumes
from apps.api.app.api.v1.saved_searches.routes import router as saved_searches

router = APIRouter()

# Authentication includes explicitly public token/bootstrap routes and account routes
# that perform their own session checks. Do not apply a router-wide candidate policy.
router.include_router(auth, prefix="/auth", tags=["authentication"])

# Every candidate workspace inherits the candidate-role gate. Resource ownership
# remains independently enforced by user_id filters in each handler/service.
candidate_policy = [Depends(require_roles("candidate"))]
router.include_router(ai, prefix="/ai", tags=["AI"], dependencies=candidate_policy)
router.include_router(
    opportunities, prefix="/opportunities", tags=["opportunities"],
    dependencies=candidate_policy,
)
router.include_router(
    automations, prefix="/automations", tags=["automation"],
    dependencies=candidate_policy,
)
router.include_router(
    profile, prefix="/profile", tags=["candidate profile"],
    dependencies=candidate_policy,
)
router.include_router(
    applications, prefix="/applications", tags=["applications"],
    dependencies=candidate_policy,
)
router.include_router(
    resumes, prefix="/resumes", tags=["resumes and CV intelligence"],
    dependencies=candidate_policy,
)
router.include_router(
    companies, prefix="/companies", tags=["companies"],
    dependencies=candidate_policy,
)
router.include_router(
    recruiters, prefix="/recruiters", tags=["recruiters"],
    dependencies=candidate_policy,
)
router.include_router(
    interviews, prefix="/interviews", tags=["interviews"],
    dependencies=candidate_policy,
)
router.include_router(
    analytics, prefix="/analytics", tags=["career analytics"],
    dependencies=candidate_policy,
)
router.include_router(
    saved_searches, prefix="/saved-searches", tags=["saved searches"],
    dependencies=candidate_policy,
)
router.include_router(
    notifications, prefix="/notifications", tags=["notifications"],
    dependencies=candidate_policy,
)
router.include_router(
    gmail, prefix="/integrations", tags=["integrations"],
    dependencies=candidate_policy,
)

# OAuth callback is validated by a short-lived, single-use state bound to the
# initiating candidate; it cannot rely on the user's browser session surviving Google redirect.
router.include_router(
    oauth_callback_router, prefix="/integrations", tags=["integrations"],
)
router.include_router(
    career_tools, prefix="/career-tools", tags=["career intelligence"],
    dependencies=candidate_policy,
)
