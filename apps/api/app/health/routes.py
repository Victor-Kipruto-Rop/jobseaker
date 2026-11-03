from fastapi import APIRouter
from apps.api.app.core.config import get_settings
from packages.ai.providers.registry import get_registry
router=APIRouter(tags=["health"])
@router.get("/health")
def health():
    s=get_settings()
    return {"status":"ok","environment":s.app_env,"automation_paused":s.global_automation_paused}
@router.get("/health/ready")
def ready(): return {"status":"ready","providers":get_registry().status()}
