"""Service orchestrating external news discovery and draft article ingestion."""

import hashlib
import logging
import re
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.articles.service import ArticlesService
from app.modules.categories.service import CategoriesService
from app.modules.news_ingestion.errors import NewsIngestionError
from app.modules.news_ingestion.guardian_client import GuardianClient
from app.modules.news_ingestion.news_content_service import NewsContentService
from app.modules.news_ingestion.schemas import (
    AdminNewsSearchDataDto,
    AdminNewsSearchQueryDto,
    AdminNewsSyncDto,
)
from app.modules.news_ingestion.types import (
    NewsSyncCounts,
    NewsSyncItem,
    NewsSyncResult,
    NormalizedNewsImportArticle,
)

logger = logging.getLogger(__name__)


def _import_slug(title: str, external_id: str, canonical_url: str) -> str:
    digest_input = f"guardian\0{external_id or canonical_url}".encode()
    suffix = hashlib.sha256(digest_input).hexdigest()[:12]
    max_base_len = 200 - len(suffix) - 1
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:max_base_len].rstrip("-")
    if not base:
        base = "article"
    return f"{base}-{suffix}"


class NewsIngestionService:
    """Service managing external news search discovery and draft ingestion."""

    def __init__(
        self,
        guardian_client: GuardianClient | None = None,
    ) -> None:
        self.guardian_client = guardian_client or GuardianClient()

    async def search(self, query: AdminNewsSearchQueryDto) -> AdminNewsSearchDataDto:
        """Discovers articles from The Guardian Content API matching the search query.

        Args:
            query (AdminNewsSearchQueryDto): Search query parameters and pagination options.

        Returns:
            AdminNewsSearchDataDto: Result set containing normalized news article items and total counts.

        Raises:
            HTTPException: When the upstream provider encounters rate limits, invalid keys, or network errors.

        Example:
            >>> # service = NewsIngestionService()
            >>> # data = await service.search(query_dto)
        """
        try:
            res = await self.guardian_client.search_metadata(
                q=query.q,
                section=query.section,
                from_date=query.from_date,
                to_date=query.to_date,
                order_by=query.order_by,
                page=query.page,
                page_size=query.page_size,
            )
            return AdminNewsSearchDataDto(
                totalArticles=res.total_articles,
                articles=res.articles,
            )
        except NewsIngestionError as err:
            self._throw_public_provider_error(err)

    async def sync(
        self,
        db: AsyncSession,
        acting_admin_id: uuid.UUID,
        dto: AdminNewsSyncDto,
    ) -> NewsSyncResult:
        """Imports discovered news articles into local draft articles.

        Args:
            db (AsyncSession): Active asynchronous database session.
            acting_admin_id (uuid.UUID): ID of the administrator performing the sync.
            dto (AdminNewsSyncDto): Sync filters, search criteria, and target category.

        Returns:
            NewsSyncResult: Synchronization statistics and list of imported/skipped/failed items.

        Raises:
            HTTPException: If category is invalid or upstream provider encounters communication failure.

        Example:
            >>> # result = await service.sync(db, admin_id, sync_dto)
        """
        if dto.default_category_id:
            await CategoriesService.require_active_category(db, dto.default_category_id)

        try:
            discovered = await self.guardian_client.search_for_import(
                q=dto.q,
                section=dto.section,
                from_date=dto.from_date,
                to_date=dto.to_date,
                order_by=dto.order_by,
                page_size=dto.page_size,
                article_ids=dto.article_ids,
            )
        except NewsIngestionError as err:
            self._throw_public_provider_error(err)

        items: list[NewsSyncItem] = []
        for article in discovered.articles:
            res_item = await self._import_one(db, acting_admin_id, dto.default_category_id, article)
            items.append(res_item)

        imported_cnt = sum(1 for i in items if i.status == "imported")
        skipped_cnt = sum(1 for i in items if i.status == "skippedDuplicate")
        failed_cnt = sum(1 for i in items if i.status == "failed")

        counts = NewsSyncCounts(
            discovered=len(items),
            imported=imported_cnt,
            skippedDuplicate=skipped_cnt,
            failed=failed_cnt,
        )

        logger.info(
            "news.ingestion.sync.completed",
            extra={
                "source": "guardian",
                "discovered": counts.discovered,
                "imported": counts.imported,
                "skippedDuplicate": counts.skipped_duplicate,
                "failed": counts.failed,
            },
        )

        return NewsSyncResult(counts=counts, items=items)

    async def _import_one(
        self,
        db: AsyncSession,
        acting_admin_id: uuid.UUID,
        default_category_id: uuid.UUID | None,
        article: NormalizedNewsImportArticle,
    ) -> NewsSyncItem:
        base = {
            "externalId": article.external_id,
            "title": article.title,
            "canonicalUrl": article.url,
        }
        created_article_id: uuid.UUID | None = None

        try:
            # 1. Check duplicate
            if await ArticlesService.find_imported_duplicate(db, article.external_id):
                return NewsSyncItem(**base, status="skippedDuplicate")

            # 2. Extract and sanitize content
            extracted = NewsContentService.resolve(article)

            # 3. Resolve category
            category_id = default_category_id
            if not category_id:
                category_id = await CategoriesService.resolve_or_create_import_category(
                    db,
                    acting_admin_id,
                    article.section_id,
                    article.section_name,
                )

            # 4. Create draft article
            summary = (article.description or extracted.plain_text)[:2000].strip()
            slug = _import_slug(article.title, article.external_id, article.url)
            created = await ArticlesService.create_imported_draft(
                db,
                acting_admin_id,
                {
                    "categoryId": category_id,
                    "title": article.title,
                    "slug": slug,
                    "summary": summary,
                    "contentHtml": extracted.content_html,
                    "externalId": article.external_id,
                    "sourcePublishedAt": article.published_at,
                    "sourceName": "The Guardian",
                    "sourceUrl": article.url,
                    "thumbnailUrl": article.image_url,
                    "authorName": article.author_name,
                },
            )
            created_article_id = created.id

            # 5. Parse content into sentences
            await ArticlesService.parse_content(db, acting_admin_id, created.id)

            return NewsSyncItem(
                **base,
                status="imported",
                articleId=str(created.id),
            )
        except Exception as err:
            # Cleanup if created
            if created_article_id:
                try:
                    await ArticlesService.delete(db, acting_admin_id, created_article_id)
                except Exception:
                    return NewsSyncItem(
                        **base,
                        status="failed",
                        errorCode="IMPORT_CLEANUP_FAILED",
                        errorMessage="Imported draft could not be safely finalized",
                    )

            error_code = "ARTICLE_IMPORT_FAILED"
            error_message = "Article import failed"
            if isinstance(err, NewsIngestionError):
                error_code = err.code
                error_message = err.message
            elif isinstance(err, HTTPException) and err.status_code < 500:
                error_code = "ARTICLE_IMPORT_REJECTED"
                error_message = "Article content could not be imported"

            return NewsSyncItem(
                **base,
                status="failed",
                errorCode=error_code,
                errorMessage=error_message,
            )

    def _throw_public_provider_error(self, err: NewsIngestionError) -> None:
        if err.code == "NEWS_PROVIDER_BAD_REQUEST":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err.message)
        if err.code == "NEWS_PROVIDER_RATE_LIMIT":
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="News provider rate limit was exceeded"
            )
        if err.code in ("NEWS_PROVIDER_AUTHENTICATION", "NEWS_PROVIDER_QUOTA"):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="News provider configuration is unavailable"
            )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="News provider request failed")
