from openai import AsyncOpenAI
from apps.api.app.core.config import get_settings
from packages.ai.providers.base import AIProvider, GenerationRequest, GenerationResult


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self):
        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is missing")
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=60.0,
            max_retries=2,
        )
        self.model = settings.openai_default_model

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        response = await self.client.responses.create(
            model=request.model or self.model,
            instructions=request.system or "",
            input=request.messages,
            max_output_tokens=request.max_tokens,
        )
        usage = response.usage
        return GenerationResult(
            text=response.output_text,
            model=response.model,
            usage={
                "input_tokens": usage.input_tokens if usage else 0,
                "output_tokens": usage.output_tokens if usage else 0,
            },
        )

    async def health_check(self) -> bool:
        # Credential presence is checked at construction; this does not make a billable API call.
        return bool(self.client.api_key)
