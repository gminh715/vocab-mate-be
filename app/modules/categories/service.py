"""Domain service managing category lifecycle, database queries, and data integrity rules."""

import math
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.articles import Article
from app.models.categories import Category
from app.modules.categories.schemas import (
    AdminCategoryDetailDataDto,
    AdminCategoryDto,
    CategoryMutationDataDto,
    CategoryStatusDto,
    CreateCategoryDto,
    PublicCategoryDto,
    UpdateCategoryDto,
    UpdateCategoryStatusDto,
)


def normalize_category_slug(slug: str) -> str:
    """Normalizes category slug by trimming whitespace and converting to lowercase.

    Args:
        slug (str): Raw slug string provided by user or provider.

    Returns:
        str: Normalized, URL-safe slug string.

    Example:
        >>> normalize_category_slug("  Tech-News  ")
        'tech-news'
    """
    return slug.strip().lower()


class CategoriesService:
    """Service providing business logic and database operations for article categories.

    Example:
        >>> # CategoriesService methods are class methods invoked with an active AsyncSession
    """

    @classmethod
    async def find_all_active(cls, db: AsyncSession, q: str | None = None) -> list[PublicCategoryDto]:
        """Retrieves all active categories ordered by displayOrder, name, and id.

        Args:
            db (AsyncSession): Active database session.
            q (str | None, optional): Optional substring filter for category name. Defaults to None.

        Returns:
            list[PublicCategoryDto]: Sequence of active category cards.

        Example:
            >>> # items = await CategoriesService.find_all_active(db, q="Science")
        """
        stmt = select(Category).where(Category.is_active.is_(True))
        if q and q.strip():
            term = f"%{q.strip()}%"
            stmt = stmt.where(Category.name.ilike(term))

        stmt = stmt.order_by(Category.display_order.asc(), Category.name.asc(), Category.id.asc())
        res = await db.execute(stmt)
        categories = res.scalars().all()
        return [
            PublicCategoryDto(
                id=c.id,
                name=c.name,
                slug=c.slug,
            )
            for c in categories
        ]

    @classmethod
    async def find_one_by_slug(cls, db: AsyncSession, slug: str) -> PublicCategoryDto:
        """Retrieves an active category by its unique URL slug.

        Args:
            db (AsyncSession): Active database session.
            slug (str): Normalized URL slug.

        Returns:
            PublicCategoryDto: Matching category data.

        Raises:
            HTTPException: 404 if no active category with the given slug exists.

        Example:
            >>> # cat = await CategoriesService.find_one_by_slug(db, "technology")
        """
        normalized = normalize_category_slug(slug)
        stmt = select(Category).where(Category.slug == normalized, Category.is_active.is_(True))
        res = await db.execute(stmt)
        category = res.scalar_one_or_none()
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found",
            )
        return PublicCategoryDto(id=category.id, name=category.name, slug=category.slug)

    @classmethod
    async def require_active_category(cls, db: AsyncSession, category_id: uuid.UUID) -> None:
        """Asserts that a target category exists and is currently active.

        Args:
            db (AsyncSession): Active database session.
            category_id (uuid.UUID): Target category unique identifier.

        Raises:
            HTTPException: 404 if category does not exist or is inactive.

        Example:
            >>> # await CategoriesService.require_active_category(db, cat_id)
        """
        stmt = select(Category).where(Category.id == category_id, Category.is_active.is_(True))
        res = await db.execute(stmt)
        if not res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Active category not found",
            )

    @classmethod
    async def find_all_admin(
        cls,
        db: AsyncSession,
        page: int,
        limit: int,
        q: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[AdminCategoryDto], dict]:
        """Retrieves a paginated list of categories for administrators.

        Args:
            db (AsyncSession): Active database session.
            page (int): 1-indexed page number.
            limit (int): Number of items per page.
            q (str | None, optional): Optional name search filter. Defaults to None.
            is_active (bool | None, optional): Optional active status filter. Defaults to None.

        Returns:
            tuple[list[AdminCategoryDto], dict]: Tuple containing items list and pagination metadata dictionary.

        Example:
            >>> # items, meta = await CategoriesService.find_all_admin(db, page=1, limit=20)
        """
        stmt = select(Category)
        count_stmt = select(func.count()).select_from(Category)

        if q and q.strip():
            term = f"%{q.strip()}%"
            stmt = stmt.where(Category.name.ilike(term))
            count_stmt = count_stmt.where(Category.name.ilike(term))

        if is_active is not None:
            stmt = stmt.where(Category.is_active == is_active)
            count_stmt = count_stmt.where(Category.is_active == is_active)

        total_res = await db.execute(count_stmt)
        total = total_res.scalar_one()

        offset = (page - 1) * limit
        stmt = (
            stmt.order_by(Category.display_order.asc(), Category.name.asc(), Category.id.asc())
            .offset(offset)
            .limit(limit)
        )
        res = await db.execute(stmt)
        categories = res.scalars().all()

        items = [
            AdminCategoryDto(
                id=c.id,
                name=c.name,
                slug=c.slug,
                description=c.description,
                isActive=c.is_active,
                displayOrder=c.display_order,
                createdAt=c.created_at,
                updatedAt=c.updated_at,
            )
            for c in categories
        ]
        meta = {
            "page": page,
            "limit": limit,
            "total": total,
            "totalPages": math.ceil(total / limit) if limit > 0 else 0,
        }
        return items, meta

    @classmethod
    async def find_one_admin(cls, db: AsyncSession, category_id: uuid.UUID) -> AdminCategoryDetailDataDto:
        """Retrieves administrative category details along with total article count.

        Args:
            db (AsyncSession): Active database session.
            category_id (uuid.UUID): Target category unique identifier.

        Returns:
            AdminCategoryDetailDataDto: Category details and associated article count.

        Raises:
            HTTPException: 404 if category is not found.

        Example:
            >>> # data = await CategoriesService.find_one_admin(db, cat_id)
        """
        stmt = select(Category).where(Category.id == category_id)
        res = await db.execute(stmt)
        category = res.scalar_one_or_none()
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found",
            )

        count_stmt = select(func.count()).select_from(Article).where(Article.category_id == category_id)
        count_res = await db.execute(count_stmt)
        article_count = count_res.scalar_one()

        return AdminCategoryDetailDataDto(
            category=AdminCategoryDto(
                id=category.id,
                name=category.name,
                slug=category.slug,
                description=category.description,
                isActive=category.is_active,
                displayOrder=category.display_order,
                createdAt=category.created_at,
                updatedAt=category.updated_at,
            ),
            articleCount=article_count,
        )

    @classmethod
    async def create(
        cls,
        db: AsyncSession,
        acting_admin_id: uuid.UUID,
        dto: CreateCategoryDto,
    ) -> CategoryMutationDataDto:
        """Creates a new category entity after validating uniqueness.

        Args:
            db (AsyncSession): Active database session.
            acting_admin_id (uuid.UUID): Authenticated admin creator identifier.
            dto (CreateCategoryDto): Payload containing category parameters.

        Returns:
            CategoryMutationDataDto: Envelope enclosing newly created category.

        Raises:
            HTTPException: 409 if category slug already exists.

        Example:
            >>> # res = await CategoriesService.create(db, admin_id, dto)
        """
        slug = normalize_category_slug(dto.slug)
        category = Category(
            id=uuid.uuid4(),
            name=dto.name.strip(),
            slug=slug,
            description=dto.description.strip() if dto.description else None,
            is_active=dto.isActive,
            display_order=dto.displayOrder,
            created_by_user_id=acting_admin_id,
            updated_by_user_id=acting_admin_id,
        )
        db.add(category)
        try:
            await db.commit()
            await db.refresh(category)
        except IntegrityError as err:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Category slug already exists",
            ) from err

        return CategoryMutationDataDto(
            category=PublicCategoryDto(id=category.id, name=category.name, slug=category.slug)
        )

    @classmethod
    async def update(
        cls,
        db: AsyncSession,
        acting_admin_id: uuid.UUID,
        category_id: uuid.UUID,
        dto: UpdateCategoryDto,
    ) -> CategoryMutationDataDto:
        """Partially updates metadata attributes of an existing category.

        Args:
            db (AsyncSession): Active database session.
            acting_admin_id (uuid.UUID): Authenticated admin modifier identifier.
            category_id (uuid.UUID): Target category unique identifier.
            dto (UpdateCategoryDto): Partial update payload.

        Returns:
            CategoryMutationDataDto: Envelope enclosing updated category.

        Raises:
            HTTPException: 400 if no fields are provided for update.
            HTTPException: 404 if category is not found.
            HTTPException: 409 if the updated slug conflicts with another category.

        Example:
            >>> # res = await CategoriesService.update(db, admin_id, cat_id, dto)
        """
        if dto.name is None and dto.slug is None and dto.description is None and dto.displayOrder is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one category field is required",
            )

        stmt = select(Category).where(Category.id == category_id)
        res = await db.execute(stmt)
        category = res.scalar_one_or_none()
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found",
            )

        if dto.name is not None:
            category.name = dto.name.strip()
        if dto.slug is not None:
            category.slug = normalize_category_slug(dto.slug)
        if dto.description is not None:
            category.description = dto.description.strip()
        if dto.displayOrder is not None:
            category.display_order = dto.displayOrder
        category.updated_by_user_id = acting_admin_id

        try:
            await db.commit()
            await db.refresh(category)
        except IntegrityError as err:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Category slug already exists",
            ) from err

        return CategoryMutationDataDto(
            category=PublicCategoryDto(id=category.id, name=category.name, slug=category.slug)
        )

    @classmethod
    async def update_status(
        cls,
        db: AsyncSession,
        acting_admin_id: uuid.UUID,
        category_id: uuid.UUID,
        dto: UpdateCategoryStatusDto,
    ) -> CategoryStatusDto:
        """Toggles the active publication status of an existing category.

        Args:
            db (AsyncSession): Active database session.
            acting_admin_id (uuid.UUID): Authenticated admin modifier identifier.
            category_id (uuid.UUID): Target category unique identifier.
            dto (UpdateCategoryStatusDto): Status update payload.

        Returns:
            CategoryStatusDto: Envelope enclosing updated status.

        Raises:
            HTTPException: 404 if category is not found.

        Example:
            >>> # res = await CategoriesService.update_status(db, admin_id, cat_id, dto)
        """
        stmt = select(Category).where(Category.id == category_id)
        res = await db.execute(stmt)
        category = res.scalar_one_or_none()
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found",
            )

        category.is_active = dto.isActive
        category.updated_by_user_id = acting_admin_id
        await db.commit()
        return CategoryStatusDto(id=category.id, isActive=category.is_active)

    @classmethod
    async def delete(
        cls,
        db: AsyncSession,
        acting_admin_id: uuid.UUID,
        category_id: uuid.UUID,
    ) -> None:
        """Deletes an unused category if no articles are referencing it.

        Args:
            db (AsyncSession): Active database session.
            acting_admin_id (uuid.UUID): Authenticated admin deleter identifier.
            category_id (uuid.UUID): Target category unique identifier.

        Raises:
            HTTPException: 404 if category is not found.
            HTTPException: 409 if category is currently referenced by articles.

        Example:
            >>> # await CategoriesService.delete(db, admin_id, cat_id)
        """
        stmt = select(Category).where(Category.id == category_id)
        res = await db.execute(stmt)
        category = res.scalar_one_or_none()
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found",
            )

        count_stmt = select(func.count()).select_from(Article).where(Article.category_id == category_id)
        count_res = await db.execute(count_stmt)
        if count_res.scalar_one() > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Category is used by articles; deactivate it instead",
            )

        try:
            await db.delete(category)
            await db.commit()
        except IntegrityError as err:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Category is used by articles; deactivate it instead",
            ) from err

    @classmethod
    async def resolve_or_create_import_category(
        cls,
        db: AsyncSession,
        acting_admin_id: uuid.UUID,
        section_id: str | None = None,
        section_name: str | None = None,
    ) -> uuid.UUID:
        """Resolves an existing active category by slug/name or creates a new active one.

        Args:
            db (AsyncSession): Active database session.
            acting_admin_id (uuid.UUID): Authenticated admin identifier.
            section_id (str | None, optional): Provider section slug/id. Defaults to None.
            section_name (str | None, optional): Provider section title. Defaults to None.

        Returns:
            uuid.UUID: Resolved or newly generated category identifier.

        Example:
            >>> # cat_id = await CategoriesService.resolve_or_create_import_category(db, admin_id, "world")
        """
        raw_slug = (section_id or section_name or "general").strip()
        slug = normalize_category_slug(raw_slug)

        stmt_slug = select(Category).where(Category.slug == slug, Category.is_active.is_(True))
        cat_slug = (await db.execute(stmt_slug)).scalar_one_or_none()
        if cat_slug:
            return cat_slug.id

        name = (section_name or section_id or "General").strip()
        stmt_name = select(Category).where(Category.name.ilike(name), Category.is_active.is_(True))
        cat_name = (await db.execute(stmt_name)).scalar_one_or_none()
        if cat_name:
            return cat_name.id

        new_cat = Category(
            id=uuid.uuid4(),
            name=name,
            slug=slug,
            is_active=True,
            display_order=0,
            created_by_user_id=acting_admin_id,
            updated_by_user_id=acting_admin_id,
        )
        db.add(new_cat)
        try:
            await db.commit()
            await db.refresh(new_cat)
            return new_cat.id
        except IntegrityError:
            await db.rollback()
            refreshed = (await db.execute(stmt_slug)).scalar_one_or_none()
            if refreshed:
                return refreshed.id
            raise
