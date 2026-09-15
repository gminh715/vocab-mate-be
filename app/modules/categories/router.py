"""Category HTTP endpoints for public catalog browsing and administrative curation."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Path, Query, Response, status

from app.common.deps import CurrentAdminDep, DbSessionDep
from app.common.response import BaseResponse, ResponseWithMeta
from app.modules.categories.schemas import (
    AdminCategoryDetailDataDto,
    AdminCategoryDto,
    CategoryDetailDataDto,
    CategoryListDataDto,
    CategoryMutationDataDto,
    CategoryStatusDto,
    CreateCategoryDto,
    UpdateCategoryDto,
    UpdateCategoryStatusDto,
)
from app.modules.categories.service import CategoriesService

router = APIRouter(prefix="/api/v1/categories", tags=["Categories"])
admin_router = APIRouter(prefix="/api/v1/admin/categories", tags=["Admin Categories"])


@router.get("", summary="Get the list of active categories")
async def get_categories(
    db: DbSessionDep,
    q: Annotated[str | None, Query(description="Optional substring filter on category title")] = None,
) -> BaseResponse[CategoryListDataDto]:
    """Retrieves all active categories ordered by display sequence and name.

    Args:
        db (AsyncSession): Active database session dependency.
        q (str | None, optional): Optional search filter. Defaults to None.

    Returns:
        BaseResponse[CategoryListDataDto]: Standard response envelope enclosing list of active categories.

    Example:
        >>> # GET /api/v1/categories?q=tech
    """
    items = await CategoriesService.find_all_active(db, q=q)
    return BaseResponse(success=True, data=CategoryListDataDto(items=items))


@router.get("/{slug}", summary="Get one active category by slug")
async def get_category_by_slug(
    db: DbSessionDep,
    slug: Annotated[str, Path(description="Unique URL-friendly slug identifier")],
) -> BaseResponse[CategoryDetailDataDto]:
    """Retrieves single active category details by URL slug.

    Args:
        db (AsyncSession): Active database session dependency.
        slug (str): Unique URL-friendly slug identifier.

    Returns:
        BaseResponse[CategoryDetailDataDto]: Standard response envelope enclosing target category.

    Example:
        >>> # GET /api/v1/categories/technology
    """
    category = await CategoriesService.find_one_by_slug(db, slug)
    return BaseResponse(success=True, data=CategoryDetailDataDto(category=category))


# ---------------------------------------------------------------------------
# Administrative Category Endpoints
# ---------------------------------------------------------------------------


@admin_router.get("", summary="List all categories (Admin)")
async def list_admin_categories(
    db: DbSessionDep,
    admin: CurrentAdminDep,
    page: Annotated[int, Query(ge=1, description="1-indexed page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    q: Annotated[str | None, Query(description="Search filter on category name")] = None,
    is_active: Annotated[bool | None, Query(alias="isActive", description="Filter by publication status")] = None,
) -> ResponseWithMeta[dict[str, list[AdminCategoryDto]], dict]:
    """Retrieves paginated category directory including active and inactive records.

    Args:
        db (AsyncSession): Active database session dependency.
        admin (User): Verified administrator user dependency.
        page (int, optional): 1-indexed page number. Defaults to 1.
        limit (int, optional): Maximum items per page. Defaults to 20.
        q (str | None, optional): Substring search over category name. Defaults to None.
        is_active (bool | None, optional): Filter by publication state. Defaults to None.

    Returns:
        ResponseWithMeta[dict[str, list[AdminCategoryDto]], dict]: Paginated categories with pagination metadata.

    Example:
        >>> # GET /api/v1/admin/categories?page=1&limit=20
    """
    items, meta = await CategoriesService.find_all_admin(db, page=page, limit=limit, q=q, is_active=is_active)
    return ResponseWithMeta(success=True, data={"items": items}, meta=meta)


@admin_router.get("/{category_id}", summary="Get category details and article count (Admin)")
async def get_admin_category(
    db: DbSessionDep,
    admin: CurrentAdminDep,
    category_id: Annotated[uuid.UUID, Path(description="Target category unique identifier")],
) -> BaseResponse[AdminCategoryDetailDataDto]:
    """Retrieves detailed administrative category record with aggregate article count.

    Args:
        db (AsyncSession): Active database session dependency.
        admin (User): Verified administrator user dependency.
        category_id (uuid.UUID): Target category unique identifier.

    Returns:
        BaseResponse[AdminCategoryDetailDataDto]: Standard response envelope with category and article count.

    Example:
        >>> # GET /api/v1/admin/categories/11111111-2222-3333-4444-555555555555
    """
    data = await CategoriesService.find_one_admin(db, category_id)
    return BaseResponse(success=True, data=data)


@admin_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a category (Admin)",
)
async def create_category(
    db: DbSessionDep,
    admin: CurrentAdminDep,
    dto: CreateCategoryDto,
) -> BaseResponse[CategoryMutationDataDto]:
    """Creates a new category entity with validation and uniqueness checks.

    Args:
        db (AsyncSession): Active database session dependency.
        admin (User): Verified administrator user dependency.
        dto (CreateCategoryDto): Payload defining category fields.

    Returns:
        BaseResponse[CategoryMutationDataDto]: Standard response envelope enclosing newly created category.

    Example:
        >>> # POST /api/v1/admin/categories with CreateCategoryDto JSON
    """
    data = await CategoriesService.create(db, admin.id, dto)
    return BaseResponse(success=True, data=data)


@admin_router.patch("/{category_id}", summary="Update a category (Admin)")
async def update_category(
    db: DbSessionDep,
    admin: CurrentAdminDep,
    category_id: Annotated[uuid.UUID, Path(description="Target category unique identifier")],
    dto: UpdateCategoryDto,
) -> BaseResponse[CategoryMutationDataDto]:
    """Performs partial update on an existing category entity.

    Args:
        db (AsyncSession): Active database session dependency.
        admin (User): Verified administrator user dependency.
        category_id (uuid.UUID): Target category unique identifier.
        dto (UpdateCategoryDto): Partial update payload.

    Returns:
        BaseResponse[CategoryMutationDataDto]: Standard response envelope enclosing updated category.

    Example:
        >>> # PATCH /api/v1/admin/categories/{id} with {"name": "Updated Tech"}
    """
    data = await CategoriesService.update(db, admin.id, category_id, dto)
    return BaseResponse(success=True, data=data)


@admin_router.patch("/{category_id}/status", summary="Activate or deactivate a category (Admin)")
async def update_category_status(
    db: DbSessionDep,
    admin: CurrentAdminDep,
    category_id: Annotated[uuid.UUID, Path(description="Target category unique identifier")],
    dto: UpdateCategoryStatusDto,
) -> BaseResponse[CategoryStatusDto]:
    """Idempotently modifies publication status for a category.

    Args:
        db (AsyncSession): Active database session dependency.
        admin (User): Verified administrator user dependency.
        category_id (uuid.UUID): Target category unique identifier.
        dto (UpdateCategoryStatusDto): Status update payload.

    Returns:
        BaseResponse[CategoryStatusDto]: Standard response envelope enclosing updated status.

    Example:
        >>> # PATCH /api/v1/admin/categories/{id}/status with {"isActive": false}
    """
    data = await CategoriesService.update_status(db, admin.id, category_id, dto)
    return BaseResponse(success=True, data=data)


@admin_router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an unused category (Admin)",
)
async def delete_category(
    db: DbSessionDep,
    admin: CurrentAdminDep,
    category_id: Annotated[uuid.UUID, Path(description="Target category unique identifier")],
) -> Response:
    """Removes an unused category if no articles reference it.

    Args:
        db (AsyncSession): Active database session dependency.
        admin (User): Verified administrator user dependency.
        category_id (uuid.UUID): Target category unique identifier.

    Returns:
        Response: HTTP 204 No Content response.

    Example:
        >>> # DELETE /api/v1/admin/categories/{id}
    """
    await CategoriesService.delete(db, admin.id, category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
