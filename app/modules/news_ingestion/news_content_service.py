"""Service for validating, sanitizing, and extracting news article HTML content."""

import re

from bs4 import BeautifulSoup

from app.core.config import settings
from app.modules.articles.helpers.html_sanitizer import HtmlSanitizerHelper
from app.modules.news_ingestion.errors import NewsIngestionError
from app.modules.news_ingestion.types import (
    ExtractedArticleContent,
    NormalizedNewsImportArticle,
)

PLACEHOLDERS = {
    "[removed]",
    "content unavailable",
    "content is unavailable",
    "not available",
    "n/a",
    "null",
    "read full article",
    "read the full article",
}

PLACEHOLDER_PREFIX = re.compile(
    r"^(?:content (?:is )?unavailable|not available|read (?:the )?full article|click here to read)",
    re.IGNORECASE,
)


def _plain_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=" ")
    return re.sub(r"\s+", " ", text).strip()


class NewsContentService:
    """Service validating external provider HTML and extracting clean markup."""

    @classmethod
    def resolve(cls, article: NormalizedNewsImportArticle) -> ExtractedArticleContent:
        """Resolves, sanitizes, and validates provider content for an imported article.

        Args:
            article (NormalizedNewsImportArticle): Normalized article data from provider.

        Returns:
            ExtractedArticleContent: Validated sanitized HTML and clean plain text representation.

        Raises:
            NewsIngestionError: If the article body is missing, exceeds size limits, or is a placeholder.

        Example:
            >>> # content = NewsContentService.resolve(normalized_article)
        """
        provider_content = article.provider_content
        if not provider_content or not provider_content.strip():
            raise NewsIngestionError("GUARDIAN_BODY_UNAVAILABLE", "Guardian article body is unavailable")

        if len(provider_content.encode("utf-8")) > settings.GUARDIAN_MAX_RESPONSE_BYTES:
            raise NewsIngestionError("GUARDIAN_BODY_UNAVAILABLE", "Guardian article body is unavailable")

        raw_plain = _plain_text_from_html(provider_content)
        if cls.is_placeholder(raw_plain):
            raise NewsIngestionError("GUARDIAN_BODY_UNAVAILABLE", "Guardian article body is unavailable")

        try:
            sanitized_html = HtmlSanitizerHelper.sanitize(provider_content)
        except Exception as err:
            raise NewsIngestionError("GUARDIAN_BODY_UNAVAILABLE", "Guardian article body is unavailable") from err

        plain_text = _plain_text_from_html(sanitized_html)
        # Check minimum characters (min 100 for safety) and letter presence
        if len(plain_text) < 100 or not re.search(r"[a-zA-Z]", plain_text) or cls.is_placeholder(plain_text):
            raise NewsIngestionError("GUARDIAN_BODY_UNAVAILABLE", "Guardian article body is unavailable")

        return ExtractedArticleContent(
            contentHtml=sanitized_html,
            plainText=plain_text,
        )

    @classmethod
    def is_placeholder(cls, text: str) -> bool:
        """Detects whether text is an unusable placeholder or paywall stub.

        Args:
            text (str): Plain text to inspect.

        Returns:
            bool: True if text matches known placeholders, False otherwise.

        Example:
            >>> NewsContentService.is_placeholder("[removed]")
            True
            >>> NewsContentService.is_placeholder("A substantial news story.")
            False
        """
        normalized = re.sub(r"\s+", " ", text).strip().lower()
        if not normalized or normalized in PLACEHOLDERS:
            return True
        if PLACEHOLDER_PREFIX.match(normalized):
            return True
        return False
