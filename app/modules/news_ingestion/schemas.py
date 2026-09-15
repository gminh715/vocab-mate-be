"""Pydantic request and response schemas for administrative news discovery and sync."""

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.modules.news_ingestion.types import (
    GuardianOrderBy,
    NewsSyncCounts,
    NewsSyncItem,
    NewsSyncResult,
    NormalizedNewsArticle,
)


class AdminNewsSearchQueryDto(BaseModel):
    """Query parameters for discovering Guardian articles."""

    model_config = ConfigDict(populate_by_name=True)

    q: str | None = Field(default=None, max_length=200)
    section: str | None = Field(default=None, max_length=100)
    from_date: str | None = Field(default=None, alias="fromDate")
    to_date: str | None = Field(default=None, alias="toDate")
    order_by: GuardianOrderBy = Field(default="newest", alias="orderBy")
    page: int = Field(default=1, ge=1, le=100)
    page_size: int = Field(default=5, ge=1, le=10, alias="pageSize")


class AdminNewsSyncDto(BaseModel):
    """Payload for importing discovered articles into draft articles."""

    model_config = ConfigDict(populate_by_name=True)

    q: str | None = Field(default=None, max_length=200)
    section: str | None = Field(default=None, max_length=100)
    from_date: str | None = Field(default=None, alias="fromDate")
    to_date: str | None = Field(default=None, alias="toDate")
    order_by: GuardianOrderBy = Field(default="newest", alias="orderBy")
    default_category_id: uuid.UUID | None = Field(default=None, alias="defaultCategoryId")
    page_size: int = Field(default=5, ge=1, le=10, alias="pageSize")
    article_ids: list[str] | None = Field(default=None, alias="articleIds")


class AdminNewsSearchDataDto(BaseModel):
    """Search discovery data wrapper."""

    model_config = ConfigDict(populate_by_name=True)

    total_articles: int = Field(alias="totalArticles")
    articles: list[NormalizedNewsArticle]


class AdminNewsSearchSuccessResponseDto(BaseModel):
    """Success response envelope for news discovery."""

    model_config = ConfigDict(populate_by_name=True)

    success: bool = True
    data: AdminNewsSearchDataDto


class AdminNewsSyncDataDto(BaseModel):
    """Sync results data payload."""

    model_config = ConfigDict(populate_by_name=True)

    counts: NewsSyncCounts
    items: list[NewsSyncItem]


class AdminNewsSyncSuccessResponseDto(BaseModel):
    """Success response envelope for news synchronization."""

    model_config = ConfigDict(populate_by_name=True)

    success: bool = True
    data: NewsSyncResult
