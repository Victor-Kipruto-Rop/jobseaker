from typing import Literal, cast

import anthropic
from anthropic.types import MessageParam

from apps.api.app.core.config import get_settings
from packages.ai.providers.base import AIProvider, GenerationRequest, GenerationResult


class AnthropicProvider(AIProvider):
    name = "anthropic"

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is missing")
        self.client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=60.0,
            max_retries=2,
        )
        self.model = settings.anthropic_default_model

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        messages: list[MessageParam] = []
        for message in request.messages:
            role = message.get("role")
            content = message.get("content")
            if role not in {"user", "assistant"} or not isinstance(content, str):
                raise ValueError(
                    "Anthropic messages require user or assistant roles and string content"
                )
            messages.append(
                {
                    "role": cast(Literal["user", "assistant"], role),
                    "content": content,
                }
            )

        response = await self.client.messages.create(
            model=request.model or self.model,
            system=request.system or "",
            messages=messages,
            max_tokens=request.max_tokens,
        )
        text = "\n".join(
            block.text
            for block in response.content
            if isinstance(block, anthropic.types.TextBlock)
        )
        return GenerationResult(
            text=text,
            model=response.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        )

    async def health_check(self) -> bool:
        # Credential presence is checked at construction; this does not make a billable API call.
        return bool(self.client.api_key)
