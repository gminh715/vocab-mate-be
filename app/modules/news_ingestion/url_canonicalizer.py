"""URL canonicalization and normalization utilities for external news articles."""

from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.modules.news_ingestion.errors import NewsIngestionError

TRACKING_PARAMETERS = {
    "fbclid",
    "gclid",
    "dclid",
    "msclkid",
    "mc_cid",
    "mc_eid",
}


def canonicalize_news_url(value: str) -> str:
    """Normalizes and canonicalizes a news article URL.

    Args:
        value (str): Raw URL string to canonicalize.

    Returns:
        str: Canonicalized URL without tracking params and with sorted query keys.

    Raises:
        NewsIngestionError: If the URL is malformed, lacks host, or contains auth credentials.

    Example:
        >>> canonicalize_news_url("https://theguardian.com/world?utm_source=fb&b=2&a=1#section")
        'https://theguardian.com/world?a=1&b=2'
    """
    try:
        parts = urlsplit(value)
    except Exception as err:
        raise NewsIngestionError("INVALID_URL", "News URL is invalid") from err

    if parts.scheme not in ("http", "https") or parts.username or parts.password or not parts.netloc:
        raise NewsIngestionError(
            "INVALID_URL",
            "News URL must use HTTP or HTTPS without credentials",
        )

    hostname = parts.netloc.lower().rstrip(".")
    query_params = parse_qsl(parts.query, keep_blank_values=True)
    filtered_params = [
        (k, v) for k, v in query_params if not k.lower().startswith("utm_") and k.lower() not in TRACKING_PARAMETERS
    ]
    filtered_params.sort(key=lambda item: item[0])
    new_query = urlencode(filtered_params)

    return urlunsplit((parts.scheme, hostname, parts.path, new_query, ""))


def try_canonicalize_news_url(value: Any) -> str | None:
    """Attempts to canonicalize a news URL, returning None on invalid inputs.

    Args:
        value (Any): Potential URL input value.

    Returns:
        str | None: Clean canonicalized URL or None if invalid.

    Example:
        >>> try_canonicalize_news_url("https://example.com?utm_medium=email")
        'https://example.com'
        >>> try_canonicalize_news_url(None) is None
        True
    """
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return canonicalize_news_url(value.strip())
    except Exception:
        return None
