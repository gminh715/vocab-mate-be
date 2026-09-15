"""Pydantic schemas and DTOs for the Collections module."""

import uuid
from datetime import datetime
from typing import Literal

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


class GetCollectionsQueryDto(BaseModel):
    """Query parameters for paginated user collections list."""

    page: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=100)
    q: str | None = Field(None, max_length=320)


class CreateCollectionDto(BaseModel):
    """Body payload for creating a user collection."""

    name: str = Field(min_length=1, max_length=100)


class UpdateCollectionDto(BaseModel):
    """Body payload for updating a user collection name."""

    name: str = Field(min_length=1, max_length=100)


class GetCollectionItemsQueryDto(BaseModel):
    """Query parameters for listing items inside a collection."""

    page: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=100)
    q: str | None = Field(None, max_length=320)
    sort: Literal["newest", "oldest"] = "newest"


class AddCollectionItemsDto(CamelModel):
    """Body payload for bulk adding vocabulary items to a collection."""

    userVocabularyIds: list[uuid.UUID] = Field(min_length=1, max_length=50)


# ---------------------------------------------------------------------------
# Response DTOs
# ---------------------------------------------------------------------------


class CollectionDto(CamelModel):
    """Base collection representation."""

    id: uuid.UUID
    name: str
    createdAt: datetime
    updatedAt: datetime


class CollectionListItemDto(CollectionDto):
    """Collection list entry with vocabulary count."""

    vocabularyCount: int


class CollectionListDataDto(CamelModel):
    """Data envelope for paginated collection listing."""

    items: list[CollectionListItemDto]
    meta: PaginationMetaDto


class CollectionDetailDataDto(CamelModel):
    """Data envelope for single collection detail."""

    collection: CollectionDto
    vocabularyCount: int


class CollectionMutationDataDto(CamelModel):
    """Data envelope for collection mutations."""

    collection: CollectionDto


class CollectionVocabularyItemDto(CamelModel):
    """Vocabulary item membership inside a collection."""

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
    addedAt: datetime


class CollectionItemsListDataDto(CamelModel):
    """Data envelope for paginated collection vocabulary items."""

    items: list[CollectionVocabularyItemDto]
    meta: PaginationMetaDto


class CollectionItemsAddDataDto(CamelModel):
    """Result data for bulk adding items to a collection."""

    addedCount: int
    skippedCount: int
