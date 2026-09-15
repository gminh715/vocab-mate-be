"""Base contracts and abstract classes for AI generation providers."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TokenUsage(BaseModel):
    """Token consumption metrics for an AI generation request."""

    model_config = ConfigDict(populate_by_name=True)

    input_tokens: int | None = Field(default=None, alias="inputTokens")
    output_tokens: int | None = Field(default=None, alias="outputTokens")


class StructuredAiRequest(BaseModel):
    """Request payload defining prompt instructions and structured JSON schema."""

    model_config = ConfigDict(populate_by_name=True)

    schema_name: str = Field(alias="schemaName")
    schema_def: dict[str, Any] = Field(alias="schema")
    system_instruction: str = Field(alias="systemInstruction")
    user_content: str = Field(alias="userContent")
    max_output_tokens: int = Field(default=4096, alias="maxOutputTokens")


class StructuredAiResponse(BaseModel):
    """Standardized response containing generated JSON string and usage telemetry."""

    content: str
    usage: TokenUsage = Field(default_factory=TokenUsage)


class BaseAiProvider(ABC):
    """Abstract interface for external AI model providers."""

    @abstractmethod
    async def generate_structured(self, request: StructuredAiRequest) -> StructuredAiResponse:
        """Dispatches a structured generation request and returns normalized JSON content."""
        pass
