"""Article HTTP endpoints for public catalog browsing, content discovery, and administrative management."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Path, Query, Response, status

from app.common.deps import CurrentAdminDep, DbSessionDep
from app.common.response import BaseResponse, ResponseWithMeta
from app.models.enums import AiGenerationStatus, ArticleStatus, CefrLevel, TermOrigin, TermReviewStatus
from app.modules.articles.schemas import (
    AdminArticleDetailDataDto,
    AdminArticleListItemDto,
    AdminArticleSentenceDetailDto,
    AdminArticleTermDetailDto,
    ArticleAnalysisDataDto,
    ArticleArchiveDataDto,
    ArticleDetailDataDto,
    ArticleMutationDataDto,
    ArticlePublishDataDto,
    ArticleRestoreDraftDataDto,
    ArticleSentenceDto,
    ArticleTermMutationDataDto,
    ArticleUpdateDataDto,
    CreateArticleDto,
    CreateArticleTermDto,
    ParseArticleContentDataDto,
    ParseArticleContentDto,
    PublicArticleCardDto,
    UpdateArticleDto,
    UpdateArticleSentenceDto,
    UpdateArticleTermDto,
)
from app.modules.articles.service import ArticlesService

router = APIRouter(prefix="/api/v1/articles", tags=["Articles"])
admin_router = APIRouter(prefix="/api/v1/admin/articles", tags=["Admin Articles"])


# ---------------------------------------------------------------------------
# Public Endpoints
# ---------------------------------------------------------------------------


@router.get("", summary="Get published articles")
async def get_articles(
    db: DbSessionDep,
    page: Annotated[int, Query(ge=1, description="1-indexed page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    q: Annotated[str | None, Query(description="Search keyword for article title")] = None,
    category_id: Annotated[uuid.UUID | None, Query(alias="categoryId", description="Filter by category ID")] = None,
    cefr_level: Annotated[CefrLevel | None, Query(alias="cefrLevel", description="Filter by CEFR level")] = None,
    sort: Annotated[str, Query(pattern="^(newest|oldest)$", description="Sort order")] = "newest",
) -> ResponseWithMeta[dict[str, list[PublicArticleCardDto]], dict]:
    """Retrieves paginated catalog of published articles matching specified criteria.

    Args:
        db (AsyncSession): Active database session dependency.
        page (int, optional): Page number. Defaults to 1.
        limit (int, optional): Items per page. Defaults to 20.
        q (str | None, optional): Search keyword. Defaults to None.
        category_id (uuid.UUID | None, optional): Category filter. Defaults to None.
        cefr_level (CefrLevel | None, optional): CEFR difficulty filter. Defaults to None.
        sort (str, optional): Ordering direction ("newest" or "oldest"). Defaults to "newest".

    Returns:
        ResponseWithMeta[dict[str, list[PublicArticleCardDto]], dict]: Enclosing article cards and pagination metadata.

    Example:
        >>> # GET /api/v1/articles?page=1&limit=20&sort=newest
    """
    items, meta = await ArticlesService.find_all_published(
        db, page=page, limit=limit, q=q, category_id=category_id, cefr_level=cefr_level, sort=sort
    )
    return ResponseWithMeta(success=True, data={"items": items}, meta=meta)


@router.get("/{slug}", summary="Get published article metadata")
async def get_article_by_slug(
    db: DbSessionDep,
    slug: Annotated[str, Path(description="Article URL slug identifier")],
) -> BaseResponse[ArticleDetailDataDto]:
    """Retrieves published article metadata and category information by URL slug.

    Args:
        db (AsyncSession): Active database session dependency.
        slug (str): Unique URL-friendly article slug.

    Returns:
        BaseResponse[ArticleDetailDataDto]: Enclosing public article details.

    Example:
        >>> # GET /api/v1/articles/quantum-computing-breakthrough
    """
    data = await ArticlesService.find_one_by_slug(db, slug)
    return BaseResponse(success=True, data=data)


# ---------------------------------------------------------------------------
# Administrative Endpoints
# ---------------------------------------------------------------------------


@admin_router.get("", summary="List articles for administration (Admin)")
async def list_admin_articles(
    db: DbSessionDep,
    admin: CurrentAdminDep,
    page: Annotated[int, Query(ge=1, description="1-indexed page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    q: Annotated[str | None, Query(description="Search keyword for article title")] = None,
    category_id: Annotated[uuid.UUID | None, Query(alias="categoryId", description="Filter by category ID")] = None,
    cefr_level: Annotated[CefrLevel | None, Query(alias="cefrLevel", description="Filter by CEFR level")] = None,
    article_status: Annotated[
        ArticleStatus | None, Query(alias="status", description="Filter by editorial status")
    ] = None,
    sort: Annotated[str, Query(pattern="^(newest|oldest)$", description="Sort order")] = "newest",
) -> ResponseWithMeta[dict[str, list[AdminArticleListItemDto]], dict]:
    """Retrieves paginated directory of articles across draft, published, and archived states.

    Args:
        db (AsyncSession): Active database session dependency.
        admin (User): Verified administrator dependency.
        page (int, optional): Page number. Defaults to 1.
        limit (int, optional): Page capacity. Defaults to 20.
        q (str | None, optional): Search keyword. Defaults to None.
        category_id (uuid.UUID | None, optional): Filter by category. Defaults to None.
        cefr_level (CefrLevel | None, optional): Filter by CEFR grade. Defaults to None.
        article_status (ArticleStatus | None, optional): Editorial state filter. Defaults to None.
        sort (str, optional): Sorting direction. Defaults to "newest".

    Returns:
        ResponseWithMeta[dict[str, list[AdminArticleListItemDto]], dict]: Paginated administrative items with metadata.

    Example:
        >>> # GET /api/v1/admin/articles?page=1&limit=20&status=DRAFT
    """
    items, meta = await ArticlesService.find_all_admin(
        db,
        page=page,
        limit=limit,
        q=q,
        category_id=category_id,
        cefr_level=cefr_level,
        article_status=article_status,
        sort=sort,
    )
    return ResponseWithMeta(success=True, data={"items": items}, meta=meta)


@admin_router.get("/{article_id}", summary="Get article administration detail (Admin)")
async def get_admin_article(
    db: DbSessionDep,
    admin: CurrentAdminDep,
    article_id: Annotated[uuid.UUID, Path(description="Target article unique identifier")],
) -> BaseResponse[AdminArticleDetailDataDto]:
    """Retrieves administrative detail of an article including raw content and sentence counts.

    Args:
        db (AsyncSession): Active database session dependency.
        admin (User): Verified administrator dependency.
        article_id (uuid.UUID): Target article unique identifier.

    Returns:
        BaseResponse[AdminArticleDetailDataDto]: Detailed article representation with counts.

    Example:
        >>> # GET /api/v1/admin/articles/11111111-2222-3333-4444-555555555555
    """
    data = await ArticlesService.find_one_admin(db, article_id)
    return BaseResponse(success=True, data=data)


@admin_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a draft article (Admin)",
)
async def create_article(
    db: DbSessionDep,
    admin: CurrentAdminDep,
    dto: CreateArticleDto,
) -> BaseResponse[ArticleMutationDataDto]:
    """Creates a new article in draft state with sanitized HTML content.

    Args:
        db (AsyncSession): Active database session dependency.
        admin (User): Verified administrator dependency.
        dto (CreateArticleDto): New article creation payload.

    Returns:
        BaseResponse[ArticleMutationDataDto]: Envelope enclosing created draft article.

    Example:
        >>> # POST /api/v1/admin/articles with CreateArticleDto JSON
    """
    data = await ArticlesService.create(db, admin.id, dto)
    return BaseResponse(success=True, data=data)


@admin_router.patch("/{article_id}", summary="Update a draft article (Admin)")
async def update_article(
    db: DbSessionDep,
    admin: CurrentAdminDep,
    article_id: Annotated[uuid.UUID, Path(description="Target article unique identifier")],
    dto: UpdateArticleDto,
) -> BaseResponse[ArticleUpdateDataDto]:
    """Partially updates metadata or content of an existing article draft.

    Args:
        db (AsyncSession): Active database session dependency.
        admin (User): Verified administrator dependency.
        article_id (uuid.UUID): Target article unique identifier.
        dto (UpdateArticleDto): Partial update payload.

    Returns:
        BaseResponse[ArticleUpdateDataDto]: Envelope enclosing updated article and contentChanged indicator.

    Example:
        >>> # PATCH /api/v1/admin/articles/{id} with {"title": "Updated Title"}
    """
    data = await ArticlesService.update(db, admin.id, article_id, dto)
    return BaseResponse(success=True, data=data)


@admin_router.post("/{article_id}/parse-content", summary="Parse article into sentences (Admin)")
async def parse_article_content(
    db: DbSessionDep,
    admin: CurrentAdminDep,
    article_id: Annotated[uuid.UUID, Path(description="Target article unique identifier")],
    dto: ParseArticleContentDto,
) -> BaseResponse[ParseArticleContentDataDto]:
    """Segments article reading text into individual sentences wrapped with span data-sentence-id.

    Args:
        db (AsyncSession): Active database session dependency.
        admin (User): Verified administrator dependency.
        article_id (uuid.UUID): Target article unique identifier.
        dto (ParseArticleContentDto): Segmentation options including force flag.

    Returns:
        BaseResponse[ParseArticleContentDataDto]: Enclosing new content version and sentence count.

    Example:
        >>> # POST /api/v1/admin/articles/{id}/parse-content with {"force": true}
    """
    data = await ArticlesService.parse_content(db, admin.id, article_id, dto)
    return BaseResponse(success=True, data=data)


@admin_router.post("/{article_id}/analyze", summary="Analyze CEFR and candidate terms (Admin)")
async def analyze_article(
    db: DbSessionDep,
    admin: CurrentAdminDep,
    article_id: Annotated[uuid.UUID, Path(description="Target article unique identifier")],
) -> BaseResponse[ArticleAnalysisDataDto]:
    """Evaluates CEFR readability grade and extracts candidate vocabulary terms for the parsed draft.

    Args:
        db (AsyncSession): Active database session dependency.
        admin (User): Verified administrator dependency.
        article_id (uuid.UUID): Target article unique identifier.

    Returns:
        BaseResponse[ArticleAnalysisDataDto]: Analysis results including CEFR grade and candidate count.

    Example:
        >>> # POST /api/v1/admin/articles/{id}/analyze
    """
    data = await ArticlesService.analyze(db, admin.id, article_id)
    return BaseResponse(success=True, data=data)


@admin_router.post("/{article_id}/publish", summary="Publish an article (Admin)")
async def publish_article(
    db: DbSessionDep,
    admin: CurrentAdminDep,
    article_id: Annotated[uuid.UUID, Path(description="Target article unique identifier")],
) -> BaseResponse[ArticlePublishDataDto]:
    """Validates editorial requirements and publishes an article to public catalog.

    Args:
        db (AsyncSession): Active database session dependency.
        admin (User): Verified administrator dependency.
        article_id (uuid.UUID): Target article unique identifier.

    Returns:
        BaseResponse[ArticlePublishDataDto]: Confirmation of publication with timestamp.

    Example:
        >>> # POST /api/v1/admin/articles/{id}/publish
    """
    data = await ArticlesService.publish(db, admin.id, article_id)
    return BaseResponse(success=True, data=data)


@admin_router.post("/{article_id}/archive", summary="Archive an article (Admin)")
async def archive_article(
    db: DbSessionDep,
    admin: CurrentAdminDep,
    article_id: Annotated[uuid.UUID, Path(description="Target article unique identifier")],
) -> BaseResponse[ArticleArchiveDataDto]:
    """Archives an article, withdrawing it from public discovery while keeping reading history intact.

    Args:
        db (AsyncSession): Active database session dependency.
        admin (User): Verified administrator dependency.
        article_id (uuid.UUID): Target article unique identifier.

    Returns:
        BaseResponse[ArticleArchiveDataDto]: Confirmation of archive status with timestamp.

    Example:
        >>> # POST /api/v1/admin/articles/{id}/archive
    """
    data = await ArticlesService.archive(db, admin.id, article_id)
    return BaseResponse(success=True, data=data)


@admin_router.post("/{article_id}/restore-draft", summary="Restore an article to draft (Admin)")
async def restore_draft_article(
    db: DbSessionDep,
    admin: CurrentAdminDep,
    article_id: Annotated[uuid.UUID, Path(description="Target article unique identifier")],
) -> BaseResponse[ArticleRestoreDraftDataDto]:
    """Restores an archived article back to draft status for editorial revisions.

    Args:
        db (AsyncSession): Active database session dependency.
        admin (User): Verified administrator dependency.
        article_id (uuid.UUID): Target article unique identifier.

    Returns:
        BaseResponse[ArticleRestoreDraftDataDto]: Confirmation of restored draft status.

    Example:
        >>> # POST /api/v1/admin/articles/{id}/restore-draft
    """
    data = await ArticlesService.restore_draft(db, admin.id, article_id)
    return BaseResponse(success=True, data=data)


# ---------------------------------------------------------------------------
# Admin Article Sentences Endpoints
# ---------------------------------------------------------------------------


@admin_router.get("/{article_id}/sentences", summary="List current-version article sentences (Admin)")
async def list_admin_sentences(
    db: DbSessionDep,
    admin: CurrentAdminDep,
    article_id: Annotated[uuid.UUID, Path(description="Target article unique identifier")],
    page: Annotated[int, Query(ge=1, description="1-indexed page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    is_active: Annotated[bool | None, Query(alias="isActive", description="Filter by active status")] = None,
) -> ResponseWithMeta[dict, dict]:
    """Retrieves paginated sentences for the current content version of an article.

    Args:
        db (AsyncSession): Active database session dependency.
        admin (User): Verified administrator dependency.
        article_id (uuid.UUID): Target article unique identifier.
        page (int, optional): Page number. Defaults to 1.
        limit (int, optional): Items per page. Defaults to 20.
        is_active (bool | None, optional): Filter by active status. Defaults to None.

    Returns:
        ResponseWithMeta[dict, dict]: Paginated sentence records and content version.

    Example:
        >>> # GET /api/v1/admin/articles/{article_id}/sentences?page=1&limit=20
    """
    items, meta, content_version = await ArticlesService.get_admin_sentences(
        db, article_id=article_id, page=page, limit=limit, is_active=is_active
    )
    return ResponseWithMeta(
        success=True,
        data={
            "items": items,
            "meta": meta,
            "contentVersion": content_version,
        },
        meta=meta,
    )


@admin_router.get(
    "/{article_id}/sentences/{sentence_id}", summary="Get a current-version sentence and its terms (Admin)"
)
async def get_admin_sentence(
    db: DbSessionDep,
    admin: CurrentAdminDep,
    article_id: Annotated[uuid.UUID, Path(description="Target article unique identifier")],
    sentence_id: Annotated[uuid.UUID, Path(description="Target sentence unique identifier")],
) -> BaseResponse[AdminArticleSentenceDetailDto]:
    """Retrieves sentence detail along with all linked contextual vocabulary terms.

    Args:
        db (AsyncSession): Active database session dependency.
        admin (User): Verified administrator dependency.
        article_id (uuid.UUID): Target article unique identifier.
        sentence_id (uuid.UUID): Target sentence unique identifier.

    Returns:
        BaseResponse[AdminArticleSentenceDetailDto]: Sentence record enclosing linked terms.

    Example:
        >>> # GET /api/v1/admin/articles/{article_id}/sentences/{sentence_id}
    """
    data = await ArticlesService.get_admin_sentence(db, article_id, sentence_id)
    return BaseResponse(success=True, data=data)


@admin_router.patch("/{article_id}/sentences/{sentence_id}", summary="Update current-version sentence metadata (Admin)")
async def update_admin_sentence(
    db: DbSessionDep,
    admin: CurrentAdminDep,
    article_id: Annotated[uuid.UUID, Path(description="Target article unique identifier")],
    sentence_id: Annotated[uuid.UUID, Path(description="Target sentence unique identifier")],
    dto: UpdateArticleSentenceDto,
) -> BaseResponse[ArticleSentenceDto]:
    """Updates Vietnamese translation or active flag for a specific sentence.

    Args:
        db (AsyncSession): Active database session dependency.
        admin (User): Verified administrator dependency.
        article_id (uuid.UUID): Target article unique identifier.
        sentence_id (uuid.UUID): Target sentence unique identifier.
        dto (UpdateArticleSentenceDto): Sentence update payload.

    Returns:
        BaseResponse[ArticleSentenceDto]: Updated sentence entity.

    Example:
        >>> # PATCH /api/v1/admin/articles/{article_id}/sentences/{sentence_id} with {"translationVi": "Dịch..."}
    """
    data = await ArticlesService.update_admin_sentence(db, admin.id, article_id, sentence_id, dto)
    return BaseResponse(success=True, data=data)


@admin_router.post(
    "/{article_id}/sentences/{sentence_id}/terms",
    status_code=status.HTTP_201_CREATED,
    summary="Create a contextual term and its HTML marker (Admin)",
)
async def create_admin_term(
    db: DbSessionDep,
    admin: CurrentAdminDep,
    article_id: Annotated[uuid.UUID, Path(description="Target article unique identifier")],
    sentence_id: Annotated[uuid.UUID, Path(description="Target sentence unique identifier")],
    dto: CreateArticleTermDto,
) -> BaseResponse[ArticleTermMutationDataDto]:
    """Creates a manual vocabulary term and injects span data-term-id marker into article HTML.

    Args:
        db (AsyncSession): Active database session dependency.
        admin (User): Verified administrator dependency.
        article_id (uuid.UUID): Target article unique identifier.
        sentence_id (uuid.UUID): Target sentence unique identifier.
        dto (CreateArticleTermDto): Term creation payload.

    Returns:
        BaseResponse[ArticleTermMutationDataDto]: Created term and content_html_changed flag.

    Example:
        >>> # POST /api/v1/admin/articles/{article_id}/sentences/{sentence_id}/terms with CreateArticleTermDto
    """
    data = await ArticlesService.create_admin_term(db, admin.id, article_id, sentence_id, dto)
    return BaseResponse(success=True, data=data)


# ---------------------------------------------------------------------------
# Admin Article Terms Endpoints
# ---------------------------------------------------------------------------


@admin_router.get("/{article_id}/terms", summary="List current-version contextual terms (Admin)")
async def list_admin_terms(
    db: DbSessionDep,
    admin: CurrentAdminDep,
    article_id: Annotated[uuid.UUID, Path(description="Target article unique identifier")],
    page: Annotated[int, Query(ge=1, description="1-indexed page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    sentence_id: Annotated[uuid.UUID | None, Query(alias="sentenceId", description="Filter by parent sentence")] = None,
    cefr_level: Annotated[CefrLevel | None, Query(alias="cefrLevel", description="Filter by CEFR grade")] = None,
    origin: Annotated[TermOrigin | None, Query(description="Filter by term origin source")] = None,
    review_status: Annotated[
        TermReviewStatus | None, Query(alias="reviewStatus", description="Filter by review status")
    ] = None,
    explanation_status: Annotated[
        AiGenerationStatus | None, Query(alias="explanationStatus", description="Filter by AI enrichment status")
    ] = None,
    is_active: Annotated[bool | None, Query(alias="isActive", description="Filter by active status")] = None,
    q: Annotated[str | None, Query(description="Search term surface value or lemma")] = None,
) -> ResponseWithMeta[dict, dict]:
    """Retrieves multi-criteria filtered listing of vocabulary terms belonging to current article version.

    Args:
        db (AsyncSession): Active database session dependency.
        admin (User): Verified administrator dependency.
        article_id (uuid.UUID): Target article unique identifier.
        page (int, optional): Page number. Defaults to 1.
        limit (int, optional): Items per page. Defaults to 20.
        sentence_id (uuid.UUID | None, optional): Parent sentence filter. Defaults to None.
        cefr_level (CefrLevel | None, optional): CEFR level filter. Defaults to None.
        origin (TermOrigin | None, optional): Origin filter. Defaults to None.
        review_status (TermReviewStatus | None, optional): Editorial review state filter. Defaults to None.
        explanation_status (AiGenerationStatus | None, optional): AI state filter. Defaults to None.
        is_active (bool | None, optional): Active state filter. Defaults to None.
        q (str | None, optional): Search keyword. Defaults to None.

    Returns:
        ResponseWithMeta[dict, dict]: Paginated terms, metadata, and contentVersion.

    Example:
        >>> # GET /api/v1/admin/articles/{article_id}/terms?page=1&limit=20
    """
    items, meta, content_version = await ArticlesService.get_admin_terms(
        db,
        article_id=article_id,
        page=page,
        limit=limit,
        sentence_id=sentence_id,
        cefr_level=cefr_level,
        origin=origin,
        review_status=review_status,
        explanation_status=explanation_status,
        is_active=is_active,
        q=q,
    )
    return ResponseWithMeta(
        success=True,
        data={
            "items": items,
            "meta": meta,
            "contentVersion": content_version,
        },
        meta=meta,
    )


@admin_router.get("/{article_id}/terms/{term_id}", summary="Get a contextual term and its parent sentence (Admin)")
async def get_admin_term(
    db: DbSessionDep,
    admin: CurrentAdminDep,
    article_id: Annotated[uuid.UUID, Path(description="Target article unique identifier")],
    term_id: Annotated[uuid.UUID, Path(description="Target vocabulary term unique identifier")],
) -> BaseResponse[AdminArticleTermDetailDto]:
    """Retrieves full contextual vocabulary term details along with parent sentence metadata.

    Args:
        db (AsyncSession): Active database session dependency.
        admin (User): Verified administrator dependency.
        article_id (uuid.UUID): Target article unique identifier.
        term_id (uuid.UUID): Target vocabulary term unique identifier.

    Returns:
        BaseResponse[AdminArticleTermDetailDto]: Detailed term representation enclosing parent sentence.

    Example:
        >>> # GET /api/v1/admin/articles/{article_id}/terms/{term_id}
    """
    data = await ArticlesService.get_admin_term(db, article_id, term_id)
    return BaseResponse(success=True, data=data)


@admin_router.patch("/{article_id}/terms/{term_id}", summary="Update contextual term metadata or marker value (Admin)")
async def update_admin_term(
    db: DbSessionDep,
    admin: CurrentAdminDep,
    article_id: Annotated[uuid.UUID, Path(description="Target article unique identifier")],
    term_id: Annotated[uuid.UUID, Path(description="Target vocabulary term unique identifier")],
    dto: UpdateArticleTermDto,
) -> BaseResponse[ArticleTermMutationDataDto]:
    """Updates lexical metadata or synchronized HTML marker text of a vocabulary term.

    Args:
        db (AsyncSession): Active database session dependency.
        admin (User): Verified administrator dependency.
        article_id (uuid.UUID): Target article unique identifier.
        term_id (uuid.UUID): Target vocabulary term unique identifier.
        dto (UpdateArticleTermDto): Term update payload.

    Returns:
        BaseResponse[ArticleTermMutationDataDto]: Mutated term and content_html_changed flag.

    Example:
        >>> # PATCH /api/v1/admin/articles/{article_id}/terms/{term_id} with UpdateArticleTermDto
    """
    data = await ArticlesService.update_admin_term(db, admin.id, article_id, term_id, dto)
    return BaseResponse(success=True, data=data)


@admin_router.post("/{article_id}/terms/{term_id}/approve", summary="Approve a pending AI term candidate (Admin)")
async def approve_admin_term(
    db: DbSessionDep,
    admin: CurrentAdminDep,
    article_id: Annotated[uuid.UUID, Path(description="Target article unique identifier")],
    term_id: Annotated[uuid.UUID, Path(description="Target vocabulary term unique identifier")],
) -> BaseResponse[ArticleTermMutationDataDto]:
    """Approves an AI term candidate, sets review_status to APPROVED, and wraps text in span data-term-id.

    Args:
        db (AsyncSession): Active database session dependency.
        admin (User): Verified administrator dependency.
        article_id (uuid.UUID): Target article unique identifier.
        term_id (uuid.UUID): Target vocabulary term unique identifier.

    Returns:
        BaseResponse[ArticleTermMutationDataDto]: Approved term and content_html_changed flag.

    Example:
        >>> # POST /api/v1/admin/articles/{article_id}/terms/{term_id}/approve
    """
    data = await ArticlesService.approve_admin_term(db, admin.id, article_id, term_id)
    return BaseResponse(success=True, data=data)


@admin_router.post("/{article_id}/terms/{term_id}/reject", summary="Reject a pending AI term candidate (Admin)")
async def reject_admin_term(
    db: DbSessionDep,
    admin: CurrentAdminDep,
    article_id: Annotated[uuid.UUID, Path(description="Target article unique identifier")],
    term_id: Annotated[uuid.UUID, Path(description="Target vocabulary term unique identifier")],
) -> BaseResponse[ArticleTermMutationDataDto]:
    """Rejects an AI term candidate without creating HTML marker tags.

    Args:
        db (AsyncSession): Active database session dependency.
        admin (User): Verified administrator dependency.
        article_id (uuid.UUID): Target article unique identifier.
        term_id (uuid.UUID): Target vocabulary term unique identifier.

    Returns:
        BaseResponse[ArticleTermMutationDataDto]: Rejected term and content_html_changed flag.

    Example:
        >>> # POST /api/v1/admin/articles/{article_id}/terms/{term_id}/reject
    """
    data = await ArticlesService.reject_admin_term(db, admin.id, article_id, term_id)
    return BaseResponse(success=True, data=data)


@admin_router.delete(
    "/{article_id}/terms/{term_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an unused contextual term and unwrap its marker (Admin)",
)
async def delete_admin_term(
    db: DbSessionDep,
    admin: CurrentAdminDep,
    article_id: Annotated[uuid.UUID, Path(description="Target article unique identifier")],
    term_id: Annotated[uuid.UUID, Path(description="Target vocabulary term unique identifier")],
) -> Response:
    """Removes an unreferenced term and unwraps its data-term-id HTML marker cleanly.

    Args:
        db (AsyncSession): Active database session dependency.
        admin (User): Verified administrator dependency.
        article_id (uuid.UUID): Target article unique identifier.
        term_id (uuid.UUID): Target vocabulary term unique identifier.

    Returns:
        Response: HTTP 204 No Content response.

    Example:
        >>> # DELETE /api/v1/admin/articles/{article_id}/terms/{term_id}
    """
    await ArticlesService.delete_admin_term(db, admin.id, article_id, term_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
