"""Admin News endpoints for Guardian article discovery and draft synchronization."""

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.common.deps import CurrentAdminDep, DbSessionDep
from app.modules.news_ingestion.schemas import (
    AdminNewsSearchQueryDto,
    AdminNewsSearchSuccessResponseDto,
    AdminNewsSyncDto,
    AdminNewsSyncSuccessResponseDto,
)
from app.modules.news_ingestion.service import NewsIngestionService

router = APIRouter(prefix="/api/v1/admin/news", tags=["Admin News"])


@router.get(
    "/search",
    response_model=AdminNewsSearchSuccessResponseDto,
    status_code=status.HTTP_200_OK,
    summary="Discover normalized Guardian articles",
)
async def search_admin_news(
    query: Annotated[AdminNewsSearchQueryDto, Query()],
    current_user: CurrentAdminDep,
    db: DbSessionDep,
) -> AdminNewsSearchSuccessResponseDto:
    """Discovers normalized Guardian articles matching query filters.

    Args:
        query (AdminNewsSearchQueryDto): Query parameters including keyword, section, date bounds, and pagination.
        current_user (User): Authenticated admin executing search.
        db (AsyncSession): Active database session dependency.

    Returns:
        AdminNewsSearchSuccessResponseDto: Discovery response containing normalized article cards.

    Example:
        >>> # GET /api/v1/admin/news/search?q=climate&pageSize=10
    """
    service = NewsIngestionService()
    data = await service.search(query)
    return AdminNewsSearchSuccessResponseDto(success=True, data=data)


@router.post(
    "/sync",
    response_model=AdminNewsSyncSuccessResponseDto,
    status_code=status.HTTP_201_CREATED,
    summary="Import discovered Guardian news as parsed drafts",
)
async def sync_admin_news(
    dto: AdminNewsSyncDto,
    current_user: CurrentAdminDep,
    db: DbSessionDep,
) -> AdminNewsSyncSuccessResponseDto:
    """Imports discovered Guardian news as local parsed drafts.

    Args:
        dto (AdminNewsSyncDto): Ingestion criteria including keywords or specific article IDs.
        current_user (User): Authenticated administrator performing the synchronization.
        db (AsyncSession): Active database session dependency.

    Returns:
        AdminNewsSyncSuccessResponseDto: Sync metrics including imported, skipped, and failed count.

    Example:
        >>> # POST /api/v1/admin/news/sync with {"q": "science", "pageSize": 5}
    """
    service = NewsIngestionService()
    res = await service.sync(db, current_user.id, dto)
    return AdminNewsSyncSuccessResponseDto(success=True, data=res)
