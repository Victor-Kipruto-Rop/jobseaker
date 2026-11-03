import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from redis import Redis
from sqlalchemy import text
from apps.api.app.core.config import get_settings
from packages.database.sessions import engine

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])

@router.get("/health")
def health():
    settings = get_settings()
    return {"status": "ok", "environment": settings.app_env,
            "automation_paused": settings.global_automation_paused}

@router.get("/health/ready")
def ready():
    settings = get_settings()
    dependencies = {"database": "error", "redis": "error"}
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        dependencies["database"] = "ok"
    except Exception:
        logger.exception("Database readiness check failed")

    try:
        client = Redis.from_url(settings.redis_url, socket_connect_timeout=2,
                                socket_timeout=2, health_check_interval=15)
        client.ping()
        client.close()
        dependencies["redis"] = "ok"
    except Exception:
        logger.exception("Redis readiness check failed")

    is_ready = all(value == "ok" for value in dependencies.values())
    return JSONResponse(
        status_code=200 if is_ready else 503,
        content={"status": "ready" if is_ready else "not_ready",
                 "dependencies": dependencies},
    )
