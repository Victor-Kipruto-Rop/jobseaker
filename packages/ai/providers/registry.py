from packages.ai.providers.mock.provider import MockProvider
from apps.api.app.core.config import get_settings
class ProviderRegistry:
    def __init__(self):
        self.providers={"mock":MockProvider()}; s=get_settings()
        if s.openai_enabled and s.openai_api_key:
            from packages.ai.providers.openai.client import OpenAIProvider
            self.providers["openai"]=OpenAIProvider()
        if s.anthropic_enabled and s.anthropic_api_key:
            from packages.ai.providers.anthropic.client import AnthropicProvider
            self.providers["anthropic"]=AnthropicProvider()
    def get(self,name=None):
        return self.providers.get(name or get_settings().ai_default_provider)
    def status(self): return {k:{"configured":True,"enabled":True} for k in self.providers}
_registry=None
def get_registry():
    global _registry
    if _registry is None: _registry=ProviderRegistry()
    return _registry
