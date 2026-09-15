"""Client adapter for communicating with The Guardian Content API."""

import asyncio
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.modules.news_ingestion.errors import NewsIngestionError
from app.modules.news_ingestion.types import (
    GuardianImportResult,
    GuardianOrderBy,
    GuardianSearchResult,
    NormalizedNewsArticle,
    NormalizedNewsImportArticle,
)
from app.modules.news_ingestion.url_canonicalizer import (
    canonicalize_news_url,
    try_canonicalize_news_url,
)

METADATA_FIELDS = "headline,trailText,byline,thumbnail"
IMPORT_FIELDS = "headline,trailText,byline,thumbnail,body"
RETRYABLE_STATUSES = {500, 502, 503, 504}


def _strip_html_tags(html: str) -> str:
    from bs4 import BeautifulSoup

    return BeautifulSoup(html, "html.parser").get_text(separator=" ").strip()


class GuardianClient:
    """Async HTTP client querying the official Guardian Content API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_ms: int | None = None,
    ) -> None:
        self.api_key = api_key or settings.GUARDIAN_API_KEY
        self.base_url = (base_url or settings.GUARDIAN_BASE_URL).rstrip("/")
        self.timeout_sec = (timeout_ms or settings.GUARDIAN_REQUEST_TIMEOUT_MS) / 1000.0

    async def search_metadata(
        self,
        q: str | None = None,
        section: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        order_by: GuardianOrderBy = "newest",
        page: int = 1,
        page_size: int = 5,
        article_ids: list[str] | None = None,
    ) -> GuardianSearchResult:
        """Discovers articles without fetching full HTML body content.

        Args:
            q (str | None, optional): Search query string. Defaults to None.
            section (str | None, optional): Section filter. Defaults to None.
            from_date (str | None, optional): ISO start date. Defaults to None.
            to_date (str | None, optional): ISO end date. Defaults to None.
            order_by (GuardianOrderBy, optional): Order direction. Defaults to "newest".
            page (int, optional): Page number. Defaults to 1.
            page_size (int, optional): Articles per page. Defaults to 5.
            article_ids (list[str] | None, optional): Specific article IDs. Defaults to None.

        Returns:
            GuardianSearchResult: Total articles count and normalized metadata articles.

        Raises:
            NewsIngestionError: If API key is missing or HTTP request fails.

        Example:
            >>> # client = GuardianClient()
            >>> # res = await client.search_metadata(q="climate")
        """
        raw_data = await self._execute_search(
            mode="metadata",
            q=q,
            section=section,
            from_date=from_date,
            to_date=to_date,
            order_by=order_by,
            page=page,
            page_size=page_size,
            article_ids=article_ids,
        )
        results = raw_data.get("results", [])
        total = raw_data.get("total", len(results))
        articles = [self._normalize_metadata(item) for item in results]
        return GuardianSearchResult(totalArticles=total, articles=articles)

    async def search_for_import(
        self,
        q: str | None = None,
        section: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        order_by: GuardianOrderBy = "newest",
        page: int = 1,
        page_size: int = 5,
        article_ids: list[str] | None = None,
    ) -> GuardianImportResult:
        """Fetches candidate articles including full HTML body content for ingestion.

        Args:
            q (str | None, optional): Search query string. Defaults to None.
            section (str | None, optional): Section filter. Defaults to None.
            from_date (str | None, optional): ISO start date. Defaults to None.
            to_date (str | None, optional): ISO end date. Defaults to None.
            order_by (GuardianOrderBy, optional): Order direction. Defaults to "newest".
            page (int, optional): Page number. Defaults to 1.
            page_size (int, optional): Articles per page. Defaults to 5.
            article_ids (list[str] | None, optional): Specific article IDs. Defaults to None.

        Returns:
            GuardianImportResult: Total articles count and normalized import articles with HTML body.

        Raises:
            NewsIngestionError: If API key is missing or HTTP request fails.

        Example:
            >>> # client = GuardianClient()
            >>> # res = await client.search_for_import(q="science", page_size=2)
        """
        raw_data = await self._execute_search(
            mode="import",
            q=q,
            section=section,
            from_date=from_date,
            to_date=to_date,
            order_by=order_by,
            page=page,
            page_size=page_size,
            article_ids=article_ids,
        )
        results = raw_data.get("results", [])
        total = raw_data.get("total", len(results))
        articles = [self._normalize_for_import(item) for item in results]
        return GuardianImportResult(totalArticles=total, articles=articles)

    async def _execute_search(
        self,
        mode: str,
        q: str | None,
        section: str | None,
        from_date: str | None,
        to_date: str | None,
        order_by: str,
        page: int,
        page_size: int,
        article_ids: list[str] | None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "page": page,
            "page-size": page_size,
            "order-by": order_by,
            "type": "article",
            "format": "json",
            "show-fields": IMPORT_FIELDS if mode == "import" else METADATA_FIELDS,
            "api-key": self.api_key,
        }
        if article_ids and len(article_ids) > 0:
            params["ids"] = ",".join(article_ids)
        else:
            if q and q.strip():
                params["q"] = q.strip()
            if section and section.strip():
                params["section"] = section.strip()

        if from_date:
            params["from-date"] = from_date
        if to_date:
            params["to-date"] = to_date

        url = f"{self.base_url}/search?{urlencode(params)}"

        last_err: Exception | None = None
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                    resp = await client.get(url, headers={"Accept": "application/json"})

                if resp.status_code in RETRYABLE_STATUSES and attempt == 0:
                    await asyncio.sleep(0.5)
                    continue

                if not resp.is_success:
                    self._map_http_status_error(resp.status_code)

                # Check body size
                body_bytes = resp.content
                if len(body_bytes) > settings.GUARDIAN_MAX_RESPONSE_BYTES:
                    raise NewsIngestionError(
                        "NEWS_PROVIDER_RESPONSE_TOO_LARGE",
                        "News provider response exceeded size safety limit",
                    )

                data = resp.json()
                if not isinstance(data, dict) or "response" not in data:
                    raise NewsIngestionError(
                        "NEWS_PROVIDER_INVALID_RESPONSE",
                        "News provider returned invalid data",
                    )
                response_obj = data["response"]
                if response_obj.get("status") != "ok" or not isinstance(response_obj.get("results"), list):
                    raise NewsIngestionError(
                        "NEWS_PROVIDER_INVALID_RESPONSE",
                        "News provider returned invalid data",
                    )
                return response_obj
            except NewsIngestionError:
                raise
            except (TimeoutError, httpx.TimeoutException) as err:
                last_err = err
                if attempt == 1:
                    raise NewsIngestionError(
                        "NEWS_PROVIDER_TIMEOUT",
                        "News provider request timed out",
                    ) from err
                await asyncio.sleep(0.25)
            except httpx.NetworkError as err:
                last_err = err
                if attempt == 1:
                    raise NewsIngestionError(
                        "NEWS_PROVIDER_NETWORK",
                        "News provider network request failed",
                    ) from err
                await asyncio.sleep(0.25)
            except Exception as err:
                raise NewsIngestionError(
                    "NEWS_PROVIDER_INVALID_RESPONSE",
                    "News provider returned invalid data",
                ) from err

        raise NewsIngestionError(
            "NEWS_PROVIDER_UPSTREAM",
            "News provider is temporarily unavailable",
        ) from last_err

    def _normalize_metadata(self, article: dict[str, Any]) -> NormalizedNewsArticle:
        fields = article.get("fields") or {}
        raw_trail = fields.get("trailText") or ""
        description = _strip_html_tags(raw_trail)[:2000].strip()

        raw_pub_date = article.get("webPublicationDate") or datetime.now(UTC).isoformat()
        try:
            pub_date = datetime.fromisoformat(raw_pub_date.replace("Z", "+00:00"))
        except Exception:
            pub_date = datetime.now(UTC)

        raw_url = article.get("webUrl") or ""
        canonical_url = canonicalize_news_url(raw_url)
        img_url = try_canonicalize_news_url(fields.get("thumbnail"))

        title = str(fields.get("headline") or article.get("webTitle") or "Untitled Article").strip()[:500]
        author = str(fields.get("byline")).strip()[:500] if fields.get("byline") else None
        sec_id = str(article.get("sectionId")).strip()[:100] if article.get("sectionId") else None
        sec_name = str(article.get("sectionName")).strip()[:200] if article.get("sectionName") else None

        return NormalizedNewsArticle(
            externalId=str(article.get("id")),
            title=title,
            description=description,
            url=canonical_url,
            imageUrl=img_url,
            sourceName="The Guardian",
            publishedAt=pub_date,
            authorName=author,
            sectionId=sec_id,
            sectionName=sec_name,
        )

    def _normalize_for_import(self, article: dict[str, Any]) -> NormalizedNewsImportArticle:
        meta = self._normalize_metadata(article)
        fields = article.get("fields") or {}
        body = fields.get("body")
        return NormalizedNewsImportArticle(
            **meta.model_dump(by_alias=True),
            providerContent=str(body) if body else None,
        )

    def _map_http_status_error(self, status_code: int) -> None:
        if status_code == 400:
            raise NewsIngestionError("NEWS_PROVIDER_BAD_REQUEST", "News provider rejected query parameters")
        if status_code in (401, 403):
            raise NewsIngestionError("NEWS_PROVIDER_AUTHENTICATION", "News provider authentication failed")
        if status_code == 429:
            raise NewsIngestionError("NEWS_PROVIDER_RATE_LIMIT", "News provider rate limit was exceeded")
        if 500 <= status_code <= 599:
            raise NewsIngestionError("NEWS_PROVIDER_UPSTREAM", "News provider server error")
        raise NewsIngestionError("NEWS_PROVIDER_INVALID_RESPONSE", f"News provider returned status {status_code}")
