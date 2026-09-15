"""FastAPI router for the Reading module managing reading progress, history, and term lookup."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response, status

from app.common.deps import CurrentUserDep, DbSessionDep
from app.common.response import BaseResponse
from app.modules.reading.schemas import (
    ContextualTermLookupDataDto,
    ReaderArticleDataDto,
    ReadingHistoryDataDto,
    ReadingHistoryQueryDto,
    ReadingProgressDataDto,
    UpdateReadingProgressDto,
)
from app.modules.reading.service import ReadingService

router = APIRouter(prefix="/api/v1/reading", tags=["Reading"])


@router.get("/history", summary="Get authenticated user reading history")
async def get_history(
    db: DbSessionDep,
    user: CurrentUserDep,
    query: Annotated[ReadingHistoryQueryDto, Depends()],
) -> BaseResponse[ReadingHistoryDataDto]:
    """Retrieves paginated reading history records for the calling learner.

    Args:
        db (AsyncSession): Active database session dependency.
        user (User): Authenticated learner user dependency.
        query (ReadingHistoryQueryDto): Query parameters for pagination and status filtering.

    Returns:
        BaseResponse[ReadingHistoryDataDto]: Envelope enclosing reading history items and pagination meta.

    Example:
        >>> # GET /api/v1/reading/history?page=1&limit=20
    """
    data = await ReadingService.get_history(db, user.id, query)
    return BaseResponse(success=True, data=data)


@router.get("/progress/{article_id}", summary="Get reading progress for an article")
async def get_progress(
    db: DbSessionDep,
    user: CurrentUserDep,
    article_id: Annotated[uuid.UUID, Path(description="Target article unique identifier")],
) -> BaseResponse[ReadingProgressDataDto]:
    """Retrieves owner-scoped reading progress or a non-persisted default progress state.

    Args:
        db (AsyncSession): Active database session dependency.
        user (User): Authenticated learner user dependency.
        article_id (uuid.UUID): Target article unique identifier.

    Returns:
        BaseResponse[ReadingProgressDataDto]: Envelope enclosing reading progress details.

    Example:
        >>> # GET /api/v1/reading/progress/11111111-2222-3333-4444-555555555555
    """
    data = await ReadingService.get_progress(db, user.id, article_id)
    return BaseResponse(success=True, data=data)


@router.put("/progress/{article_id}", summary="Update reading progress for an article")
async def update_progress(
    db: DbSessionDep,
    user: CurrentUserDep,
    article_id: Annotated[uuid.UUID, Path(description="Target article unique identifier")],
    dto: UpdateReadingProgressDto,
) -> BaseResponse[ReadingProgressDataDto]:
    """Creates or updates owner-scoped reading progress percentage and last read sentence.

    Args:
        db (AsyncSession): Active database session dependency.
        user (User): Authenticated learner user dependency.
        article_id (uuid.UUID): Target article unique identifier.
        dto (UpdateReadingProgressDto): Progress update values.

    Returns:
        BaseResponse[ReadingProgressDataDto]: Envelope enclosing updated reading progress.

    Example:
        >>> # PUT /api/v1/reading/progress/{article_id} with {"progressPercent": 50}
    """
    data = await ReadingService.update_progress(db, user.id, article_id, dto)
    return BaseResponse(success=True, data=data)


@router.post("/progress/{article_id}/complete", summary="Mark reading progress as completed")
async def complete_progress(
    db: DbSessionDep,
    user: CurrentUserDep,
    article_id: Annotated[uuid.UUID, Path(description="Target article unique identifier")],
) -> BaseResponse[ReadingProgressDataDto]:
    """Marks article reading progress as 100% completed and stamps completion time.

    Args:
        db (AsyncSession): Active database session dependency.
        user (User): Authenticated learner user dependency.
        article_id (uuid.UUID): Target article unique identifier.

    Returns:
        BaseResponse[ReadingProgressDataDto]: Envelope enclosing completed reading progress.

    Example:
        >>> # POST /api/v1/reading/progress/{article_id}/complete
    """
    data = await ReadingService.complete_progress(db, user.id, article_id)
    return BaseResponse(success=True, data=data)


@router.delete(
    "/progress/{article_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete reading progress for an article",
)
async def delete_progress(
    db: DbSessionDep,
    user: CurrentUserDep,
    article_id: Annotated[uuid.UUID, Path(description="Target article unique identifier")],
) -> Response:
    """Removes stored reading progress for an article, resetting it to default.

    Args:
        db (AsyncSession): Active database session dependency.
        user (User): Authenticated learner user dependency.
        article_id (uuid.UUID): Target article unique identifier.

    Returns:
        Response: HTTP 204 No Content response.

    Example:
        >>> # DELETE /api/v1/reading/progress/{article_id}
    """
    await ReadingService.delete_progress(db, user.id, article_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/articles/{slug}", summary="Get personalized reader article data")
async def get_reader_article(
    db: DbSessionDep,
    user: CurrentUserDep,
    slug: Annotated[str, Path(description="Target article URL slug identifier")],
) -> BaseResponse[ReaderArticleDataDto]:
    """Retrieves reader article data including sanitized HTML and CEFR highlights.

    Args:
        db (AsyncSession): Active database session dependency.
        user (User): Authenticated learner user dependency.
        slug (str): Unique URL-friendly slug of the published article.

    Returns:
        BaseResponse[ReaderArticleDataDto]: Envelope enclosing personalized reader data.

    Example:
        >>> # GET /api/v1/reading/articles/quantum-computing
    """
    data = await ReadingService.get_reader_article(db, user.id, slug)
    return BaseResponse(success=True, data=data)


@router.get("/articles/{article_id}/terms/{term_id}", summary="Lookup term in article sentence context")
async def get_contextual_term(
    db: DbSessionDep,
    user: CurrentUserDep,
    article_id: Annotated[uuid.UUID, Path(description="Target article unique identifier")],
    term_id: Annotated[uuid.UUID, Path(description="Target vocabulary term unique identifier")],
) -> BaseResponse[ContextualTermLookupDataDto]:
    """Retrieves enriched vocabulary details and enclosing sentence context for a term marker.

    Args:
        db (AsyncSession): Active database session dependency.
        user (User): Authenticated learner user dependency.
        article_id (uuid.UUID): Target article unique identifier.
        term_id (uuid.UUID): Target vocabulary term unique identifier.

    Returns:
        BaseResponse[ContextualTermLookupDataDto]: Envelope enclosing term details, parent sentence, and save state.

    Example:
        >>> # GET /api/v1/reading/articles/{article_id}/terms/{term_id}
    """
    data = await ReadingService.get_contextual_term(db, user.id, article_id, term_id)
    return BaseResponse(success=True, data=data)
