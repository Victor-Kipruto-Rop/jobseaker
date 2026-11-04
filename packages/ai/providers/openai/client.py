from typing import Any, Literal, cast

from openai import AsyncOpenAI
from openai.types.responses import EasyInputMessageParam

from apps.api.app.core.config import get_settings
from packages.ai.providers.base import AIProvider, GenerationRequest, GenerationResult


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self) -> None:
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
        messages: list[EasyInputMessageParam] = []
        allowed_roles = {"user", "assistant", "system", "developer"}
        for message in request.messages:
            role = message.get("role")
            content = message.get("content")
            if role not in allowed_roles or not isinstance(content, str):
                raise ValueError("AI messages require a supported role and string content")
            messages.append(
                {
                    "role": cast(
                        Literal["user", "assistant", "system", "developer"], role
                    ),
                    "content": content,
                }
            )

        response = await self.client.responses.create(
            model=request.model or self.model,
            instructions=request.system or "",
            # The SDK's generated input union is list-invariant; message shape is
            # validated above, so isolate the typing mismatch at this SDK boundary.
            input=cast(Any, messages),
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
