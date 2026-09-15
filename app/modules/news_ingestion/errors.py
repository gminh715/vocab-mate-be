"""Error definitions for the news ingestion module."""

from typing import Literal

NewsIngestionErrorCode = Literal[
    "NEWS_PROVIDER_BAD_REQUEST",
    "NEWS_PROVIDER_AUTHENTICATION",
    "NEWS_PROVIDER_QUOTA",
    "NEWS_PROVIDER_RATE_LIMIT",
    "NEWS_PROVIDER_UPSTREAM",
    "NEWS_PROVIDER_NETWORK",
    "NEWS_PROVIDER_TIMEOUT",
    "NEWS_PROVIDER_INVALID_RESPONSE",
    "NEWS_PROVIDER_RESPONSE_TOO_LARGE",
    "GUARDIAN_BODY_UNAVAILABLE",
    "INVALID_URL",
]


class NewsIngestionError(Exception):
    """Domain error representing news discovery, fetch, extraction, or validation failures."""

    def __init__(self, code: NewsIngestionErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
