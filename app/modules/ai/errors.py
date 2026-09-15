"""AI domain errors and provider failure categorization."""

from typing import Literal

ProviderFailureReason = Literal[
    "timeout",
    "rate-limit",
    "server",
    "request",
    "configuration",
    "network",
    "unusable-output",
]

FALLBACK_ELIGIBLE_REASONS: set[ProviderFailureReason] = {
    "timeout",
    "rate-limit",
    "server",
    "network",
    "unusable-output",
}


def is_fallback_eligible(reason: ProviderFailureReason) -> bool:
    """Returns True if failure reason warrants failover to secondary provider."""
    return reason in FALLBACK_ELIGIBLE_REASONS


class AiError(Exception):
    """Domain exception raised when AI generation or validation fails."""

    def __init__(self, code: str, message: str, reason: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.reason = reason


class ProviderCallError(Exception):
    """Low-level error thrown by AI provider adapters."""

    def __init__(self, reason: ProviderFailureReason, original_error: Exception | None = None) -> None:
        super().__init__(f"Provider call failed: {reason}")
        self.reason = reason
        self.original_error = original_error
