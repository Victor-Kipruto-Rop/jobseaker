from packages.ai.providers.mock.provider import MockProvider
from apps.api.app.core.config import get_settings


class ProviderRegistry:
    def __init__(self):
        self.providers = {"mock": MockProvider()}
        settings = get_settings()
        if settings.openai_enabled and settings.openai_api_key:
            from packages.ai.providers.openai.client import OpenAIProvider
            self.providers["openai"] = OpenAIProvider()
        if settings.anthropic_enabled and settings.anthropic_api_key:
            from packages.ai.providers.anthropic.client import AnthropicProvider
            self.providers["anthropic"] = AnthropicProvider()

    def get(self, name=None):
        return self.providers.get(name or get_settings().ai_default_provider)


_registry = None


def get_registry():
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry


def reset_registry():
    """Reset after configuration changes in tests or controlled local reloads."""
    global _registry
    _registry = None
