"""Secondary/fallback AI provider adapter communicating with Groq."""

import asyncio
from typing import Any

import groq
from groq import AsyncGroq

from app.core.config import settings
from app.modules.ai.errors import ProviderCallError, ProviderFailureReason
from app.modules.ai.providers.base import (
    BaseAiProvider,
    StructuredAiRequest,
    StructuredAiResponse,
    TokenUsage,
)

GROQ_STRICT_SCHEMA_MODELS = {
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
}


def _normalize_groq_schema(schema: Any) -> Any:
    """Recursively removes maxItems which is unsupported by Groq strict mode."""
    if isinstance(schema, list):
        return [_normalize_groq_schema(item) for item in schema]
    if isinstance(schema, dict):
        return {k: _normalize_groq_schema(v) for k, v in schema.items() if k != "maxItems"}
    return schema


def _classify_status(status: int) -> ProviderFailureReason:
    if status == 408:
        return "timeout"
    if status in (413, 429):
        return "rate-limit"
    if 500 <= status <= 599:
        return "server"
    if status in (400, 422):
        return "request"
    if 400 <= status <= 499:
        return "configuration"
    return "request"


def _classify_groq_error(error: Exception) -> ProviderFailureReason:
    if isinstance(error, (groq.APIConnectionTimeoutError, asyncio.TimeoutError)):
        return "timeout"
    if isinstance(error, groq.APIConnectionError):
        return "network"
    if isinstance(error, groq.APIError):
        # Check for json_validate_failed
        body = getattr(error, "body", None)
        if isinstance(body, dict):
            err_dict = body.get("error")
            if isinstance(err_dict, dict) and err_dict.get("code") == "json_validate_failed":
                return "unusable-output"
        status = getattr(error, "status_code", None)
        if isinstance(status, int):
            return _classify_status(status)
    return "request"


class GroqAiProvider(BaseAiProvider):
    """Secondary/fallback AI provider adapter using Groq."""

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout_ms: int | None = None) -> None:
        self.api_key = api_key or settings.GROQ_API_KEY
        self.model = model or settings.GROQ_MODEL
        self.timeout_ms = timeout_ms or settings.AI_REQUEST_TIMEOUT_MS
        self._client: AsyncGroq | None = None

    @property
    def client(self) -> AsyncGroq:
        """The lazy-initialized AsyncGroq client instance."""
        if not self._client:
            if not self.api_key:
                raise ProviderCallError("configuration")
            self._client = AsyncGroq(
                api_key=self.api_key,
                timeout=self.timeout_ms / 1000.0,
                max_retries=1,
            )
        return self._client

    async def generate_structured(self, request: StructuredAiRequest) -> StructuredAiResponse:
        """Generates structured output with an internal retry on unusable response."""
        last_error = ProviderCallError("unusable-output")
        for attempt in range(2):
            try:
                return await self._generate_once(request)
            except ProviderCallError as err:
                last_error = err
                if err.reason != "unusable-output" or attempt == 1:
                    raise
            except Exception as err:
                reason = _classify_groq_error(err)
                last_error = ProviderCallError(reason, original_error=err)
                if reason != "unusable-output" or attempt == 1:
                    raise last_error from err
        raise last_error

    async def _generate_once(self, request: StructuredAiRequest) -> StructuredAiResponse:
        supports_strict = self.model in GROQ_STRICT_SCHEMA_MODELS
        groq_schema = _normalize_groq_schema(request.schema_def)

        schema_instruction = (
            f"{request.system_instruction} "
            f"Return exactly one JSON object matching this JSON Schema: "
            f"{request.schema_def}"
        )

        messages = [
            {
                "role": "system",
                "content": request.system_instruction if supports_strict else schema_instruction,
            },
            {"role": "user", "content": request.user_content},
        ]

        response_format: dict[str, Any] = (
            {
                "type": "json_schema",
                "json_schema": {
                    "name": request.schema_name,
                    "strict": True,
                    "schema": groq_schema,
                },
            }
            if supports_strict
            else {"type": "json_object"}
        )

        try:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.0,
                "seed": 0,
                "n": 1,
                "max_completion_tokens": request.max_output_tokens,
                "response_format": response_format,
            }
            if supports_strict:
                kwargs["reasoning_effort"] = "low"

            resp = await self.client.chat.completions.create(**kwargs)
            content = resp.choices[0].message.content if resp.choices else None
            if not content or not content.strip():
                raise ProviderCallError("unusable-output")

            input_tokens = resp.usage.prompt_tokens if resp.usage else None
            output_tokens = resp.usage.completion_tokens if resp.usage else None

            return StructuredAiResponse(
                content=content,
                usage=TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens),
            )
        except ProviderCallError:
            raise
        except Exception as err:
            reason = _classify_groq_error(err)
            raise ProviderCallError(reason, original_error=err) from err
