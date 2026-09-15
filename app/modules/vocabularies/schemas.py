"""Pydantic schemas and DTOs for the Vocabularies module."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.models.enums import CefrLevel


class CamelModel(BaseModel):
    """Base model enforcing camelCase serialization."""

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )


class PaginationMetaDto(CamelModel):
    """Pagination metadata model."""

    page: int
    limit: int
    total: int
    totalPages: int


# ---------------------------------------------------------------------------
# Request DTOs
# ---------------------------------------------------------------------------


class GetVocabulariesQueryDto(BaseModel):
    """Query parameters for filtered personal vocabulary list."""

    page: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=100)
    q: str | None = Field(None, max_length=320)
    cefrLevel: CefrLevel | None = None
    collectionId: uuid.UUID | None = None
    sort: Literal["newest", "oldest"] = "newest"


class SaveVocabularyDto(CamelModel):
    """Body payload for capturing a contextual term as a saved vocabulary item."""

    articleSentenceTermId: uuid.UUID
    collectionIds: list[uuid.UUID] = Field(min_length=1, max_length=50)


# ---------------------------------------------------------------------------
# Response DTOs
# ---------------------------------------------------------------------------


class VocabularyCollectionSummaryDto(CamelModel):
    """Lightweight summary of an associated collection."""

    id: uuid.UUID
    name: str
    addedAt: datetime


class VocabularySnapshotDto(CamelModel):
    """Base learning snapshot fields."""

    id: uuid.UUID
    articleSentenceTermId: uuid.UUID
    savedWordDisplay: str
    savedLemma: str
    savedPartOfSpeech: str
    savedIpa: str | None = None
    savedCefrLevel: CefrLevel
    savedMeaningVi: str
    definitionEn: str | None = None
    savedAt: datetime
    createdAt: datetime


class VocabularyListItemDto(VocabularySnapshotDto):
    """List item enriched with collection memberships."""

    collections: list[VocabularyCollectionSummaryDto] = Field(default_factory=list)


class VocabularyDetailDto(VocabularySnapshotDto):
    """Full detail view with contextual examples."""

    savedExamples: list[dict[str, Any]] = Field(default_factory=list)


class VocabularySourceArticleDto(CamelModel):
    """Lightweight source article navigation metadata."""

    id: uuid.UUID
    slug: str
    title: str
    thumbnailUrl: str | None = None
    sourceName: str | None = None
    sourceUrl: str | None = None


class VocabularyListDataDto(CamelModel):
    """Data envelope for paginated vocabulary list."""

    items: list[VocabularyListItemDto]
    meta: PaginationMetaDto


class VocabularyDetailDataDto(CamelModel):
    """Data envelope for single vocabulary detail with article context."""

    vocabulary: VocabularyDetailDto
    collections: list[VocabularyCollectionSummaryDto]
    sourceArticle: VocabularySourceArticleDto


class VocabularySaveDataDto(CamelModel):
    """Data envelope for save vocabulary mutation response."""

    vocabulary: VocabularyDetailDto
    collections: list[VocabularyCollectionSummaryDto]
