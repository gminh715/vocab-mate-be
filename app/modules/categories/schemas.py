"""Data transfer objects and request/response schemas for category operations."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PublicCategoryDto(BaseModel):
    """Publicly visible category card representation.

    Attributes:
        id (uuid.UUID): Unique category identifier.
        name (str): Human-readable category display title.
        slug (str): Unique URL-friendly slug identifier.

    Example:
        >>> cat = PublicCategoryDto(id=uuid.uuid4(), name="Technology", slug="technology")
        >>> cat.name
        'Technology'
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str


class CategoryListDataDto(BaseModel):
    """Payload envelope for the active public category catalog.

    Attributes:
        items (list[PublicCategoryDto]): Sequence of active categories.

    Example:
        >>> data = CategoryListDataDto(items=[])
        >>> len(data.items)
        0
    """

    items: list[PublicCategoryDto]


class CategoryDetailDataDto(BaseModel):
    """Payload envelope for individual category detail queries.

    Attributes:
        category (PublicCategoryDto): Target category information.

    Example:
        >>> cat = PublicCategoryDto(id=uuid.uuid4(), name="Science", slug="science")
        >>> data = CategoryDetailDataDto(category=cat)
        >>> data.category.slug
        'science'
    """

    category: PublicCategoryDto


class AdminCategoryDto(PublicCategoryDto):
    """Administrative representation of a category including internal metadata.

    Attributes:
        id (uuid.UUID): Unique category identifier.
        name (str): Human-readable category display title.
        slug (str): Unique URL-friendly slug identifier.
        description (str | None): Extended description or editorial notes.
        isActive (bool): Whether the category is visible in the public catalog.
        displayOrder (int): Priority order for sorting categories in catalog views.
        createdAt (datetime): Entity creation timestamp.
        updatedAt (datetime): Entity last modification timestamp.

    Example:
        >>> cat = AdminCategoryDto(
        ...     id=uuid.uuid4(),
        ...     name="Tech",
        ...     slug="tech",
        ...     description="Tech news",
        ...     isActive=True,
        ...     displayOrder=1,
        ...     createdAt=datetime.now(),
        ...     updatedAt=datetime.now(),
        ... )
        >>> cat.isActive
        True
    """

    description: str | None = None
    isActive: bool
    displayOrder: int
    createdAt: datetime
    updatedAt: datetime


class AdminCategoryListDataDto(BaseModel):
    """Payload envelope for administrative category directory listings.

    Attributes:
        items (list[AdminCategoryDto]): Sequence of administrative category entries.

    Example:
        >>> data = AdminCategoryListDataDto(items=[])
        >>> len(data.items)
        0
    """

    items: list[AdminCategoryDto]


class AdminCategoryDetailDataDto(BaseModel):
    """Payload envelope for administrative category details with aggregate metrics.

    Attributes:
        category (AdminCategoryDto): Target category entity data.
        articleCount (int): Total count of articles associated with this category.

    Example:
        >>> cat = AdminCategoryDto(
        ...     id=uuid.uuid4(),
        ...     name="Tech",
        ...     slug="tech",
        ...     isActive=True,
        ...     displayOrder=1,
        ...     createdAt=datetime.now(),
        ...     updatedAt=datetime.now(),
        ... )
        >>> data = AdminCategoryDetailDataDto(category=cat, articleCount=12)
        >>> data.articleCount
        12
    """

    category: AdminCategoryDto
    articleCount: int


class CategoryMutationDataDto(BaseModel):
    """Payload envelope returned following category creation or update mutations.

    Attributes:
        category (PublicCategoryDto): Mutated category summary.

    Example:
        >>> cat = PublicCategoryDto(id=uuid.uuid4(), name="Tech", slug="tech")
        >>> data = CategoryMutationDataDto(category=cat)
        >>> data.category.name
        'Tech'
    """

    category: PublicCategoryDto


class CategoryStatusDto(BaseModel):
    """Payload envelope returned following category status toggle operations.

    Attributes:
        id (uuid.UUID): Target category unique identifier.
        isActive (bool): Updated publication/active status flag.

    Example:
        >>> status_dto = CategoryStatusDto(id=uuid.uuid4(), isActive=False)
        >>> status_dto.isActive
        False
    """

    id: uuid.UUID
    isActive: bool


class CreateCategoryDto(BaseModel):
    """Payload for creating a new article category.

    Attributes:
        name (str): Category title (1-100 characters).
        slug (str): Unique URL-friendly slug (1-100 characters).
        description (str | None): Optional editorial description (max 500 characters).
        isActive (bool): Publication status flag. Defaults to True.
        displayOrder (int): Display sequence order (>= 0). Defaults to 0.

    Example:
        >>> dto = CreateCategoryDto(name="Business", slug="business")
        >>> dto.name
        'Business'
    """

    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    isActive: bool = True
    displayOrder: int = Field(0, ge=0)


class UpdateCategoryDto(BaseModel):
    """Payload for updating an existing article category.

    Attributes:
        name (str | None): Optional new category title (1-100 characters).
        slug (str | None): Optional new URL slug (1-100 characters).
        description (str | None): Optional updated description (max 500 characters).
        displayOrder (int | None): Optional updated display sequence order (>= 0).

    Example:
        >>> dto = UpdateCategoryDto(name="Global Business")
        >>> dto.name
        'Global Business'
    """

    name: str | None = Field(None, min_length=1, max_length=100)
    slug: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    displayOrder: int | None = Field(None, ge=0)


class UpdateCategoryStatusDto(BaseModel):
    """Payload for activating or deactivating an article category.

    Attributes:
        isActive (bool): Updated publication status.

    Example:
        >>> dto = UpdateCategoryStatusDto(isActive=False)
        >>> dto.isActive
        False
    """

    isActive: bool
