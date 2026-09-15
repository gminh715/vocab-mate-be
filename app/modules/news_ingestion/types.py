"""Type definitions and Pydantic schemas for the news ingestion module."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

GuardianOrderBy = Literal["newest", "oldest", "relevance"]
GUARDIAN_ORDER_BY: tuple[GuardianOrderBy, ...] = ("newest", "oldest", "relevance")


class NormalizedNewsArticle(BaseModel):
    """Normalized metadata for a discovered news article from The Guardian."""

    model_config = ConfigDict(populate_by_name=True)

    external_id: str = Field(alias="externalId")
    title: str
    description: str
    url: str
    image_url: str | None = Field(default=None, alias="imageUrl")
    source_name: str = Field(alias="sourceName")
    published_at: datetime = Field(alias="publishedAt")
    author_name: str | None = Field(default=None, alias="authorName")
    section_id: str | None = Field(default=None, alias="sectionId")
    section_name: str | None = Field(default=None, alias="sectionName")


class NormalizedNewsImportArticle(NormalizedNewsArticle):
    """Importable article including raw provider content body."""

    provider_content: str | None = Field(default=None, alias="providerContent")


class ExtractedArticleContent(BaseModel):
    """Validated and sanitized article content bundle."""

    model_config = ConfigDict(populate_by_name=True)

    content_html: str = Field(alias="contentHtml")
    plain_text: str = Field(alias="plainText")


class GuardianSearchResult(BaseModel):
    """Discovery search results bundle."""

    model_config = ConfigDict(populate_by_name=True)

    total_articles: int = Field(alias="totalArticles")
    articles: list[NormalizedNewsArticle]


class GuardianImportResult(BaseModel):
    """Candidate articles with full body content for draft importation."""

    model_config = ConfigDict(populate_by_name=True)

    total_articles: int = Field(alias="totalArticles")
    articles: list[NormalizedNewsImportArticle]


class NewsSyncItem(BaseModel):
    """Processing outcome for an individual imported article."""

    model_config = ConfigDict(populate_by_name=True)

    status: Literal["imported", "skippedDuplicate", "failed"]
    external_id: str = Field(alias="externalId")
    title: str
    canonical_url: str = Field(alias="canonicalUrl")
    article_id: str | None = Field(default=None, alias="articleId")
    error_code: str | None = Field(default=None, alias="errorCode")
    error_message: str | None = Field(default=None, alias="errorMessage")


class NewsSyncCounts(BaseModel):
    """Aggregate metrics counting discovered, imported, skipped, and failed news items."""

    model_config = ConfigDict(populate_by_name=True)

    discovered: int
    imported: int
    skipped_duplicate: int = Field(alias="skippedDuplicate")
    failed: int


class NewsSyncResult(BaseModel):
    """Result of news sync operation."""

    model_config = ConfigDict(populate_by_name=True)

    counts: NewsSyncCounts
    items: list[NewsSyncItem]
