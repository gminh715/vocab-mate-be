"""Primary AI provider adapter for Google Gemini via the official SDK."""

import asyncio

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.core.config import settings
from app.modules.ai.errors import ProviderCallError, ProviderFailureReason
from app.modules.ai.providers.base import (
    BaseAiProvider,
    StructuredAiRequest,
    StructuredAiResponse,
    TokenUsage,
)

GEMINI_MINIMAL_THINKING_MODELS = (
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-3-flash",
)

GEMINI_DISABLED_THINKING_MODELS = (
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
)


def _gemini_thinking_config(model: str) -> types.ThinkingConfig | None:
    for supported in GEMINI_MINIMAL_THINKING_MODELS:
        if model.startswith(supported):
            return types.ThinkingConfig(thinking_level="MINIMAL")
    for supported in GEMINI_DISABLED_THINKING_MODELS:
        if model.startswith(supported):
            return types.ThinkingConfig(thinking_budget=0)
    return None


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


def _classify_gemini_error(error: Exception) -> ProviderFailureReason:
    if isinstance(error, (asyncio.TimeoutError, httpx.TimeoutException)):
        return "timeout"
    if isinstance(error, httpx.NetworkError):
        return "network"
    if isinstance(error, genai_errors.APIError):
        status = getattr(error, "code", None)
        if isinstance(status, int):
            return _classify_status(status)
    return "request"


class GeminiAiProvider(BaseAiProvider):
    """Primary AI provider communicating with Google Gemini."""

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout_ms: int | None = None) -> None:
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        self.timeout_ms = timeout_ms or settings.AI_REQUEST_TIMEOUT_MS
        self._client: genai.Client | None = None

    @property
    def client(self) -> genai.Client:
        """The lazy-initialized Google GenAI client instance."""
        if not self._client:
            if not self.api_key:
                raise ProviderCallError("configuration")
            self._client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(
                    timeout=self.timeout_ms,
                ),
            )
        return self._client

    async def generate_structured(self, request: StructuredAiRequest) -> StructuredAiResponse:
        """Generates structured JSON output using Gemini's response_schema."""
        try:
            config = types.GenerateContentConfig(
                system_instruction=request.system_instruction,
                candidate_count=1,
                max_output_tokens=request.max_output_tokens,
                response_mime_type="application/json",
                response_json_schema=request.schema_def,
                thinking_config=_gemini_thinking_config(self.model),
            )
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=request.user_content,
                config=config,
            )
            if not response or not response.text:
                raise ProviderCallError("unusable-output")

            input_tokens = None
            output_tokens = None
            if response.usage_metadata:
                input_tokens = getattr(response.usage_metadata, "prompt_token_count", None)
                output_tokens = getattr(response.usage_metadata, "candidates_token_count", None)

            return StructuredAiResponse(
                content=response.text,
                usage=TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens),
            )
        except ProviderCallError:
            raise
        except Exception as err:
            reason = _classify_gemini_error(err)
            raise ProviderCallError(reason, original_error=err) from err
