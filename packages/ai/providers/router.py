import logging
from apps.api.app.core.config import get_settings
from packages.ai.providers.registry import get_registry
from packages.ai.providers.base import GenerationRequest, GenerationResult

logger = logging.getLogger(__name__)


async def generate_with_fallback(
    request: GenerationRequest, preferred: str | None = None
) -> GenerationResult:
    settings = get_settings()
    registry = get_registry()
    candidates = []
    for name in (preferred or settings.ai_default_provider, settings.ai_fallback_provider):
        if name and name not in candidates:
            candidates.append(name)
    last_error = None
    for name in candidates:
        provider = registry.get(name)
        if provider is None:
            logger.warning("AI provider is not configured", extra={"provider": name})
            continue
        try:
            return await provider.generate(request)
        except Exception as exc:
            last_error = exc
            logger.exception("AI provider request failed", extra={"provider": name})
    if settings.app_env in {"local", "development", "test"}:
        mock = registry.get("mock")
        if mock is not None and "mock" not in candidates:
            return await mock.generate(request)
    raise RuntimeError("No configured AI provider could complete the request") from last_error
