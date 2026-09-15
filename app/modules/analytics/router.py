"""HTTP router endpoints for learner self-study analytics and administrative metrics."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.common.deps import CurrentAdminDep, CurrentUserDep, DbSessionDep
from app.common.response import BaseResponse, api_response
from app.models.enums import UserStatus
from app.modules.analytics.admin_service import AdminAnalyticsService
from app.modules.analytics.learner_service import LearnerAnalyticsService
from app.modules.analytics.schemas import (
    AdminAnalyticsOverviewDataDto,
    AdminContentAnalyticsDataDto,
    AdminContentAnalyticsQueryDto,
    AdminUserAnalyticsDataDto,
    AdminUserAnalyticsQueryDto,
    AnalyticsDateRangeQueryDto,
    AnalyticsGroupBy,
    AnalyticsOverviewDataDto,
    ReadingAnalyticsDataDto,
    ReviewAnalyticsDataDto,
    VocabularyAnalyticsDataDto,
    VocabularyAnalyticsQueryDto,
)

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])
admin_router = APIRouter(prefix="/api/v1/admin/analytics", tags=["Admin Analytics"])


# ---------------------------------------------------------------------------
# Learner Analytics Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/me/overview",
    summary="Get authenticated learner overview",
    response_model=BaseResponse[AnalyticsOverviewDataDto],
)
@router.get(
    "/overview",
    summary="Get learner overview (alias)",
    response_model=BaseResponse[AnalyticsOverviewDataDto],
    include_in_schema=False,
)
async def get_learner_overview(
    db: DbSessionDep,
    current_user: CurrentUserDep,
    from_time: Annotated[
        str | None,
        Query(alias="from", description="Range start ISO timestamp"),
    ] = None,
    to_time: Annotated[
        str | None,
        Query(alias="to", description="Range end ISO timestamp"),
    ] = None,
) -> BaseResponse[AnalyticsOverviewDataDto]:
    """Retrieves high-level summary metrics for the authenticated learner.

    Args:
        db (AsyncSession): Active database session dependency.
        current_user (User): Authenticated learner user entity.
        from_time (str | None, optional): Range start timestamp. Defaults to None.
        to_time (str | None, optional): Range end timestamp. Defaults to None.

    Returns:
        BaseResponse[AnalyticsOverviewDataDto]: Formatted overview payload.

    Example:
        >>> # resp = await get_learner_overview(db, current_user)
    """
    query = AnalyticsDateRangeQueryDto(from_time=from_time, to_time=to_time)
    data = await LearnerAnalyticsService.get_overview(
        db=db,
        user_id=current_user.id,
        query=query,
    )
    return api_response(data)


@router.get(
    "/me/vocabulary",
    summary="Get learner vocabulary acquisition metrics",
    response_model=BaseResponse[VocabularyAnalyticsDataDto],
)
async def get_learner_vocabulary_analytics(
    db: DbSessionDep,
    current_user: CurrentUserDep,
    from_time: Annotated[
        str | None,
        Query(alias="from", description="Range start ISO timestamp"),
    ] = None,
    to_time: Annotated[
        str | None,
        Query(alias="to", description="Range end ISO timestamp"),
    ] = None,
    group_by: Annotated[
        AnalyticsGroupBy | None,
        Query(alias="groupBy", description="Trend bucket granularity (DAY, WEEK, MONTH)"),
    ] = None,
) -> BaseResponse[VocabularyAnalyticsDataDto]:
    """Retrieves CEFR mastery distribution, FSRS states, and time series buckets.

    Args:
        db (AsyncSession): Active database session dependency.
        current_user (User): Authenticated learner user entity.
        from_time (str | None, optional): Range start timestamp. Defaults to None.
        to_time (str | None, optional): Range end timestamp. Defaults to None.
        group_by (AnalyticsGroupBy | None, optional): Aggregation bucket. Defaults to None.

    Returns:
        BaseResponse[VocabularyAnalyticsDataDto]: Vocabulary analytics metrics.

    Example:
        >>> # resp = await get_learner_vocabulary_analytics(db, current_user)
    """
    query = VocabularyAnalyticsQueryDto(
        from_time=from_time,
        to_time=to_time,
        groupBy=group_by,
    )
    data = await LearnerAnalyticsService.get_vocabulary_analytics(
        db=db,
        user_id=current_user.id,
        query=query,
    )
    return api_response(data)


@router.get(
    "/me/reading",
    summary="Get learner reading volume metrics",
    response_model=BaseResponse[ReadingAnalyticsDataDto],
)
async def get_learner_reading_analytics(
    db: DbSessionDep,
    current_user: CurrentUserDep,
    from_time: Annotated[
        str | None,
        Query(alias="from", description="Range start ISO timestamp"),
    ] = None,
    to_time: Annotated[
        str | None,
        Query(alias="to", description="Range end ISO timestamp"),
    ] = None,
    group_by: Annotated[
        AnalyticsGroupBy | None,
        Query(alias="groupBy", description="Trend bucket granularity (DAY, WEEK, MONTH)"),
    ] = None,
) -> BaseResponse[ReadingAnalyticsDataDto]:
    """Retrieves reading volume, completion ratios, category breakdown, and time series.

    Args:
        db (AsyncSession): Active database session dependency.
        current_user (User): Authenticated learner user entity.
        from_time (str | None, optional): Range start timestamp. Defaults to None.
        to_time (str | None, optional): Range end timestamp. Defaults to None.
        group_by (AnalyticsGroupBy | None, optional): Aggregation bucket. Defaults to None.

    Returns:
        BaseResponse[ReadingAnalyticsDataDto]: Reading analytics metrics.

    Example:
        >>> # resp = await get_learner_reading_analytics(db, current_user)
    """
    query = AnalyticsDateRangeQueryDto(from_time=from_time, to_time=to_time)
    data = await LearnerAnalyticsService.get_reading_analytics(
        db=db,
        user_id=current_user.id,
        query=query,
    )
    return api_response(data)


@router.get(
    "/me/review",
    summary="Get learner FSRS review and streak metrics",
    response_model=BaseResponse[ReviewAnalyticsDataDto],
)
async def get_learner_review_analytics(
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> BaseResponse[ReviewAnalyticsDataDto]:
    """Retrieves tutor session reviews, accuracy, retention rate, streaks, and recent days.

    Args:
        db (AsyncSession): Active database session dependency.
        current_user (User): Authenticated learner user entity.

    Returns:
        BaseResponse[ReviewAnalyticsDataDto]: Review velocity metrics.

    Example:
        >>> # resp = await get_learner_review_analytics(db, current_user)
    """
    data = await LearnerAnalyticsService.get_review_analytics(
        db=db,
        user_id=current_user.id,
    )
    return api_response(data)


# ---------------------------------------------------------------------------
# Administrative Analytics Endpoints
# ---------------------------------------------------------------------------


@admin_router.get(
    "/overview",
    summary="Get administrative platform overview",
    response_model=BaseResponse[AdminAnalyticsOverviewDataDto],
)
async def get_admin_overview(
    db: DbSessionDep,
    admin: CurrentAdminDep,
    from_time: Annotated[
        str | None,
        Query(alias="from", description="Range start ISO timestamp"),
    ] = None,
    to_time: Annotated[
        str | None,
        Query(alias="to", description="Range end ISO timestamp"),
    ] = None,
) -> BaseResponse[AdminAnalyticsOverviewDataDto]:
    """Retrieves system-wide user counts, active users, articles, and saved vocabulary flow.

    Args:
        db (AsyncSession): Active database session dependency.
        admin (User): Authenticated administrator user entity.
        from_time (str | None, optional): Range start timestamp. Defaults to None.
        to_time (str | None, optional): Range end timestamp. Defaults to None.

    Returns:
        BaseResponse[AdminAnalyticsOverviewDataDto]: System-wide overview numbers.

    Example:
        >>> # resp = await get_admin_overview(db, admin)
    """
    query = AnalyticsDateRangeQueryDto(from_time=from_time, to_time=to_time)
    data = await AdminAnalyticsService.get_admin_overview(db=db, query=query)
    return api_response(data)


@admin_router.get(
    "/content",
    summary="Get administrative content analytics",
    response_model=BaseResponse[AdminContentAnalyticsDataDto],
)
async def get_admin_content_analytics(
    db: DbSessionDep,
    admin: CurrentAdminDep,
    from_time: Annotated[
        str | None,
        Query(alias="from", description="Range start ISO timestamp"),
    ] = None,
    to_time: Annotated[
        str | None,
        Query(alias="to", description="Range end ISO timestamp"),
    ] = None,
    category_id: Annotated[
        uuid.UUID | None,
        Query(alias="categoryId", description="Filter metrics by category ID"),
    ] = None,
) -> BaseResponse[AdminContentAnalyticsDataDto]:
    """Retrieves article catalog status distribution, category breakdown, and top rankings.

    Args:
        db (AsyncSession): Active database session dependency.
        admin (User): Authenticated administrator user entity.
        from_time (str | None, optional): Range start timestamp. Defaults to None.
        to_time (str | None, optional): Range end timestamp. Defaults to None.
        category_id (uuid.UUID | None, optional): Category filter. Defaults to None.

    Returns:
        BaseResponse[AdminContentAnalyticsDataDto]: Content engagement analytics.

    Example:
        >>> # resp = await get_admin_content_analytics(db, admin)
    """
    query = AdminContentAnalyticsQueryDto(
        from_time=from_time,
        to_time=to_time,
        categoryId=category_id,
    )
    data = await AdminAnalyticsService.get_admin_content_analytics(db=db, query=query)
    return api_response(data)


@admin_router.get(
    "/users",
    summary="Get administrative user cohort analytics",
    response_model=BaseResponse[AdminUserAnalyticsDataDto],
)
async def get_admin_user_analytics(
    db: DbSessionDep,
    admin: CurrentAdminDep,
    from_time: Annotated[
        str | None,
        Query(alias="from", description="Range start ISO timestamp"),
    ] = None,
    to_time: Annotated[
        str | None,
        Query(alias="to", description="Range end ISO timestamp"),
    ] = None,
    status: Annotated[
        UserStatus | None,
        Query(description="Filter metrics by account status"),
    ] = None,
) -> BaseResponse[AdminUserAnalyticsDataDto]:
    """Retrieves user status breakdown, learning profiles, registration trends, and retention.

    Args:
        db (AsyncSession): Active database session dependency.
        admin (User): Authenticated administrator user entity.
        from_time (str | None, optional): Range start timestamp. Defaults to None.
        to_time (str | None, optional): Range end timestamp. Defaults to None.
        status (UserStatus | None, optional): User status filter. Defaults to None.

    Returns:
        BaseResponse[AdminUserAnalyticsDataDto]: User activity and cohort analytics.

    Example:
        >>> # resp = await get_admin_user_analytics(db, admin)
    """
    query = AdminUserAnalyticsQueryDto(
        from_time=from_time,
        to_time=to_time,
        status=status,
    )
    data = await AdminAnalyticsService.get_admin_user_analytics(db=db, query=query)
    return api_response(data)
