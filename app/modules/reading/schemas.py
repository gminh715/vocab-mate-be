"""Pydantic schemas and data transfer objects for learner reading and progress tracking."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.models.enums import AiGenerationStatus, ArticleStatus, CefrLevel, ReadingStatus
from app.modules.articles.schemas import PublicArticleMetadataDto
from app.modules.categories.schemas import PublicCategoryDto


class CamelModel(BaseModel):
    """Base model enforcing camelCase JSON serialization and ORM attribute reading.

    Example:
        >>> class ExampleDto(CamelModel):
        ...     my_field: str
        >>> obj = ExampleDto(my_field="test")
        >>> obj.model_dump(by_alias=True)
        {'myField': 'test'}
    """

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )


class PaginationMetaDto(CamelModel):
    """Pagination metadata model for reading history listings.

    Attributes:
        page (int): Current 1-indexed page.
        limit (int): Requested maximum item capacity.
        total (int): Total matched records.
        totalPages (int): Calculated total pages.

    Example:
        >>> meta = PaginationMetaDto(page=1, limit=10, total=25, totalPages=3)
        >>> meta.totalPages
        3
    """

    page: int
    limit: int
    total: int
    totalPages: int


# ---------------------------------------------------------------------------
# Request DTOs
# ---------------------------------------------------------------------------


class ReadingHistoryQueryDto(BaseModel):
    """Query parameter model for filtering and paginating reading history.

    Attributes:
        page (int): 1-indexed page number (>= 1).
        limit (int): Page size limit (1-100).
        status (ReadingStatus | None): Optional filter for reading progress status.
        sort (Literal['newest', 'oldest']): Sort ordering by read timestamp.

    Example:
        >>> query = ReadingHistoryQueryDto(page=1, limit=20, sort="newest")
        >>> query.sort
        'newest'
    """

    page: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=100)
    status: ReadingStatus | None = None
    sort: Literal["newest", "oldest"] = "newest"


class UpdateReadingProgressDto(CamelModel):
    """Payload for updating learner reading progress on an article.

    Attributes:
        progressPercent (Decimal): Reading completion percentage (0.0 to 100.0).
        lastSentenceOrder (int | None): Order of the last read sentence (>= 1).
        readingSeconds (int | None): Incremental seconds spent reading (>= 0).

    Example:
        >>> dto = UpdateReadingProgressDto(progressPercent=Decimal("75.5"), lastSentenceOrder=12)
        >>> dto.progressPercent
        Decimal('75.5')
    """

    progressPercent: Decimal = Field(ge=0, le=100)
    lastSentenceOrder: int | None = Field(None, ge=1)
    readingSeconds: int | None = Field(None, ge=0)


# ---------------------------------------------------------------------------
# Reading Progress Response DTOs
# ---------------------------------------------------------------------------


class ReaderProgressDto(CamelModel):
    """Reading progress state information for a specific article.

    Attributes:
        articleId (uuid.UUID): Target article unique identifier.
        status (ReadingStatus): Current reading status (READING, COMPLETED).
        progressPercent (float): Completion percentage between 0.0 and 100.0.
        completedAt (datetime | None): Timestamp when article was marked complete.

    Example:
        >>> prog = ReaderProgressDto(
        ...     articleId=uuid.uuid4(),
        ...     status=ReadingStatus.READING,
        ...     progressPercent=50.0,
        ... )
        >>> prog.status
        <ReadingStatus.READING: 'READING'>
    """

    articleId: uuid.UUID
    status: ReadingStatus
    progressPercent: float
    completedAt: datetime | None = None


class ReadingProgressDataDto(CamelModel):
    """Payload envelope for individual article reading progress queries.

    Attributes:
        progress (ReaderProgressDto): Progress state data.

    Example:
        >>> prog = ReaderProgressDto(
        ...     articleId=uuid.uuid4(),
        ...     status=ReadingStatus.READING,
        ...     progressPercent=0.0,
        ... )
        >>> data = ReadingProgressDataDto(progress=prog)
        >>> data.progress.progressPercent
        0.0
    """

    progress: ReaderProgressDto


# ---------------------------------------------------------------------------
# Reading History Response DTOs
# ---------------------------------------------------------------------------


class ReadingHistoryArticleDto(CamelModel):
    """Article summary within reading history items.

    Attributes:
        id (uuid.UUID): Article unique identifier.
        title (str): Article display headline.
        slug (str): Unique URL slug.
        summary (str): Brief article teaser.
        thumbnailUrl (str | None): Optional hero image URL.
        cefrLevel (CefrLevel): Assessed CEFR difficulty grade.
        status (ArticleStatus): Editorial publication state.
        publishedAt (datetime | None): Public release timestamp.
        category (PublicCategoryDto): Associated category card.

    Example:
        >>> cat = PublicCategoryDto(id=uuid.uuid4(), name="Tech", slug="tech")
        >>> art = ReadingHistoryArticleDto(
        ...     id=uuid.uuid4(),
        ...     title="AI Boom",
        ...     slug="ai-boom",
        ...     summary="Overview",
        ...     cefrLevel=CefrLevel.B2,
        ...     status=ArticleStatus.PUBLISHED,
        ...     category=cat,
        ... )
        >>> art.title
        'AI Boom'
    """

    id: uuid.UUID
    title: str
    slug: str
    summary: str
    thumbnailUrl: str | None = None
    cefrLevel: CefrLevel
    status: ArticleStatus
    publishedAt: datetime | None = None
    category: PublicCategoryDto


class ReadingHistoryItemDto(CamelModel):
    """Individual record within a user's reading history listing.

    Attributes:
        articleId (uuid.UUID): Article unique identifier.
        status (ReadingStatus): Current reading progress state.
        progressPercent (float): Completion percentage (0.0 - 100.0).
        completedAt (datetime | None): Optional completion timestamp.
        firstOpenedAt (datetime): Initial opening timestamp.
        lastReadAt (datetime): Most recent reading session timestamp.
        article (ReadingHistoryArticleDto): Nested article summary.

    Example:
        >>> # ReadingHistoryItemDto instances are loaded from UserArticleProgress models
    """

    articleId: uuid.UUID
    status: ReadingStatus
    progressPercent: float
    completedAt: datetime | None = None
    firstOpenedAt: datetime
    lastReadAt: datetime
    article: ReadingHistoryArticleDto


class ReadingHistoryDataDto(CamelModel):
    """Data envelope for paginated reading history listings.

    Attributes:
        items (list[ReadingHistoryItemDto]): Sequence of history items.
        meta (PaginationMetaDto): Pagination metadata.

    Example:
        >>> meta = PaginationMetaDto(page=1, limit=20, total=0, totalPages=0)
        >>> data = ReadingHistoryDataDto(items=[], meta=meta)
        >>> len(data.items)
        0
    """

    items: list[ReadingHistoryItemDto]
    meta: PaginationMetaDto


# ---------------------------------------------------------------------------
# Reader Article Response DTOs
# ---------------------------------------------------------------------------


class ReaderArticleDto(PublicArticleMetadataDto):
    """Reader article metadata including category card.

    Attributes:
        category (PublicCategoryDto): Associated category details.

    Example:
        >>> # ReaderArticleDto extends PublicArticleMetadataDto
    """

    category: PublicCategoryDto


class ReaderArticleDataDto(CamelModel):
    """Personalized reader article payload including sanitized HTML and terms.

    Attributes:
        article (ReaderArticleDto): Base article metadata.
        contentHtml (str): Sanitized HTML content annotated with sentence and term markers.
        highlightedTermIds (list[str]): List of term UUIDs matching learner CEFR highlights.
        progress (ReaderProgressDto): Current learner progress on this article.

    Example:
        >>> # Constructed by ReadingService.get_reader_article
    """

    article: ReaderArticleDto
    contentHtml: str
    highlightedTermIds: list[str]
    progress: ReaderProgressDto


# ---------------------------------------------------------------------------
# Contextual Term Lookup Response DTOs
# ---------------------------------------------------------------------------


class ContextualTermDto(CamelModel):
    """Enriched vocabulary term details for contextual lookup modal.

    Attributes:
        id (uuid.UUID): Term unique identifier.
        value (str): Surface form as it appears in the sentence.
        lemma (str): Dictionary base lemma.
        partOfSpeech (str | None): Grammatical tag.
        ipa (str | None): Phonetic transcription.
        cefrLevel (CefrLevel | None): Lexical difficulty grade.
        contextualMeaningVi (str | None): Contextual Vietnamese translation.
        definitionEn (str | None): English dictionary definition.
        contextualExplanation (str | None): Editorial or AI usage note.
        explanationStatus (AiGenerationStatus): Readiness status of AI enrichment.
        synonyms (list[str]): Related synonymous terms.
        antonyms (list[str]): Antonymous terms.
        collocations (list[str]): Typical word pairings.
        relatedTerms (list[str]): Conceptually related lemmas.
        examples (list[dict[str, Any]]): Sentence usage demonstrations.

    Example:
        >>> term = ContextualTermDto(
        ...     id=uuid.uuid4(),
        ...     value="revolution",
        ...     lemma="revolution",
        ...     explanationStatus=AiGenerationStatus.READY,
        ... )
        >>> term.lemma
        'revolution'
    """

    id: uuid.UUID
    value: str
    lemma: str
    partOfSpeech: str | None = None
    ipa: str | None = None
    cefrLevel: CefrLevel | None = None
    contextualMeaningVi: str | None = None
    definitionEn: str | None = None
    contextualExplanation: str | None = None
    explanationStatus: AiGenerationStatus
    synonyms: list[str] = Field(default_factory=list)
    antonyms: list[str] = Field(default_factory=list)
    collocations: list[str] = Field(default_factory=list)
    relatedTerms: list[str] = Field(default_factory=list)
    examples: list[dict[str, Any]] = Field(default_factory=list)


class ContextualParentSentenceDto(CamelModel):
    """Sentence context enclosing the active vocabulary term occurrence.

    Attributes:
        id (uuid.UUID): Sentence unique identifier.
        sentenceOrder (int): Position within the article (1-indexed).
        sentenceText (str): Plain English text of the sentence.
        translationVi (str | None): Vietnamese sentence translation.

    Example:
        >>> s = ContextualParentSentenceDto(
        ...     id=uuid.uuid4(),
        ...     sentenceOrder=1,
        ...     sentenceText="The experiment succeeded.",
        ... )
        >>> s.sentenceOrder
        1
    """

    id: uuid.UUID
    sentenceOrder: int
    sentenceText: str
    translationVi: str | None = None


class ContextualTermSaveStateDto(CamelModel):
    """Status indicating whether a term is currently saved in learner vocabulary.

    Attributes:
        isSaved (bool): Whether the user has saved this term occurrence.
        userVocabularyId (uuid.UUID | None): Identifier of the saved record if saved.

    Example:
        >>> state = ContextualTermSaveStateDto(isSaved=False)
        >>> state.isSaved
        False
    """

    isSaved: bool
    userVocabularyId: uuid.UUID | None = None


class ContextualTermLookupDataDto(CamelModel):
    """Full payload for the reader term lookup popup drawer.

    Attributes:
        term (ContextualTermDto): Enriched vocabulary details.
        parentSentence (ContextualParentSentenceDto): Enclosing sentence context.
        saveState (ContextualTermSaveStateDto): Learner save/collection bookmark status.

    Example:
        >>> # Created by ReadingService.get_contextual_term
    """

    term: ContextualTermDto
    parentSentence: ContextualParentSentenceDto
    saveState: ContextualTermSaveStateDto
