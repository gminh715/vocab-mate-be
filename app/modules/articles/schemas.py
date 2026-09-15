"""Data transfer objects and request/response schemas for article domain operations."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.models.enums import AiGenerationStatus, ArticleStatus, CefrLevel, TermOrigin, TermReviewStatus
from app.modules.categories.schemas import PublicCategoryDto


class CamelModel(BaseModel):
    """Base model enforcing camelCase serialization and ORM attribute reading.

    Example:
        >>> class ExampleModel(CamelModel):
        ...     my_field: str
        >>> obj = ExampleModel(my_field="sample")
        >>> obj.model_dump(by_alias=True)
        {'myField': 'sample'}
    """

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )


class PublicArticleCardDto(CamelModel):
    """Publicly displayed article summary card.

    Attributes:
        id (uuid.UUID): Article unique identifier.
        title (str): Article headline.
        slug (str): Unique URL slug.
        summary (str): Short summary snippet.
        thumbnail_url (str | None): URL to article hero thumbnail.
        cefr_level (CefrLevel): Assessed CEFR difficulty grade.
        published_at (datetime | None): Public release timestamp.
        category (PublicCategoryDto): Associated category card.

    Example:
        >>> cat = PublicCategoryDto(id=uuid.uuid4(), name="Tech", slug="tech")
        >>> card = PublicArticleCardDto(
        ...     id=uuid.uuid4(),
        ...     title="AI Boom",
        ...     slug="ai-boom",
        ...     summary="Brief summary",
        ...     cefr_level=CefrLevel.B2,
        ...     category=cat,
        ... )
        >>> card.title
        'AI Boom'
    """

    id: uuid.UUID
    title: str
    slug: str
    summary: str
    thumbnail_url: str | None = None
    cefr_level: CefrLevel
    published_at: datetime | None = None
    category: PublicCategoryDto


class PublicArticleMetadataDto(CamelModel):
    """Detailed article metadata for reader headers.

    Attributes:
        id (uuid.UUID): Article unique identifier.
        title (str): Full article headline.
        slug (str): URL slug.
        summary (str): Introductory summary text.
        source_name (str | None): Original publisher name.
        source_url (str | None): External canonical link.
        author_name (str | None): Bylined author name.
        thumbnail_url (str | None): Main image link.
        cefr_level (CefrLevel): CEFR reading difficulty.
        status (ArticleStatus): Editorial status (PUBLISHED).
        published_at (datetime | None): Publication date and time.

    Example:
        >>> meta = PublicArticleMetadataDto(
        ...     id=uuid.uuid4(),
        ...     title="Space Frontier",
        ...     slug="space-frontier",
        ...     summary="Exploring deep space.",
        ...     cefr_level=CefrLevel.B1,
        ...     status=ArticleStatus.PUBLISHED,
        ... )
        >>> meta.status
        <ArticleStatus.PUBLISHED: 'PUBLISHED'>
    """

    id: uuid.UUID
    title: str
    slug: str
    summary: str
    source_name: str | None = None
    source_url: str | None = None
    author_name: str | None = None
    thumbnail_url: str | None = None
    cefr_level: CefrLevel
    status: ArticleStatus
    published_at: datetime | None = None


class ArticleListDataDto(BaseModel):
    """Payload envelope for article catalog listings.

    Attributes:
        items (list[PublicArticleCardDto]): Sequence of article summary cards.

    Example:
        >>> data = ArticleListDataDto(items=[])
        >>> len(data.items)
        0
    """

    items: list[PublicArticleCardDto]


class ArticleDetailDataDto(BaseModel):
    """Payload envelope for public article detail view.

    Attributes:
        article (PublicArticleMetadataDto): Article metadata.
        category (PublicCategoryDto): Associated category card.

    Example:
        >>> # Created when reading article metadata
    """

    article: PublicArticleMetadataDto
    category: PublicCategoryDto


class AdminArticleListItemDto(PublicArticleCardDto):
    """Administrative article catalog item including editorial audit fields.

    Attributes:
        category_id (uuid.UUID): Foreign key to category.
        external_id (str | None): Provider identifier.
        source_published_at (datetime | None): Provider original timestamp.
        ai_analysis_status (AiGenerationStatus | None): AI enrichment job status.
        ai_analysis_error (str | None): Last error message from AI jobs.
        status (ArticleStatus): Full editorial status.
        content_version (int): Incremental content version counter.
        archived_at (datetime | None): Archive timestamp if archived.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Modification timestamp.

    Example:
        >>> # AdminArticleListItemDto instances loaded in administrative lists
    """

    category_id: uuid.UUID
    external_id: str | None = None
    source_published_at: datetime | None = None
    ai_analysis_status: AiGenerationStatus | None = None
    ai_analysis_error: str | None = None
    status: ArticleStatus
    content_version: int
    archived_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AdminArticleDto(CamelModel):
    """Detailed administrative article entity including raw content HTML.

    Attributes:
        id (uuid.UUID): Article unique identifier.
        category_id (uuid.UUID): Associated category identifier.
        title (str): Article title.
        slug (str): Unique URL slug.
        summary (str): Editorial summary.
        content_html (str): Complete article HTML text.
        content_version (int): Content revision counter.
        source_name (str | None): Source publisher.
        source_url (str | None): Source URL.
        author_name (str | None): Author byline.
        thumbnail_url (str | None): Hero thumbnail link.
        external_id (str | None): Provider identifier.
        source_published_at (datetime | None): Provider publish date.
        ai_analysis_status (AiGenerationStatus | None): AI processing state.
        ai_analysis_error (str | None): Diagnostic error text.
        cefr_level (CefrLevel): Lexical difficulty rating.
        status (ArticleStatus): Editorial lifecycle stage.
        published_at (datetime | None): Release timestamp.
        archived_at (datetime | None): Archive timestamp.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Modification timestamp.
        category (PublicCategoryDto): Embedded category card.

    Example:
        >>> # AdminArticleDto represents full editorial article state
    """

    id: uuid.UUID
    category_id: uuid.UUID
    title: str
    slug: str
    summary: str
    content_html: str
    content_version: int
    source_name: str | None = None
    source_url: str | None = None
    author_name: str | None = None
    thumbnail_url: str | None = None
    external_id: str | None = None
    source_published_at: datetime | None = None
    ai_analysis_status: AiGenerationStatus | None = None
    ai_analysis_error: str | None = None
    cefr_level: CefrLevel
    status: ArticleStatus
    published_at: datetime | None = None
    archived_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    category: PublicCategoryDto


class AdminArticleDetailDataDto(BaseModel):
    """Payload envelope for detailed administrative article view with sentence counts.

    Attributes:
        article (AdminArticleDto): Administrative article data.
        sentenceCount (int): Number of parsed sentence spans.
        termCount (int): Number of identified vocabulary terms.

    Example:
        >>> # AdminArticleDetailDataDto loaded in admin article editor
    """

    article: AdminArticleDto
    sentenceCount: int
    termCount: int


class CreateArticleDto(BaseModel):
    """Payload for creating a new article draft.

    Attributes:
        categoryId (uuid.UUID): Associated category foreign identifier.
        title (str): Headline text (1-300 characters).
        slug (str): URL slug formatted in lower-kebab-case (1-200 characters).
        summary (str): Brief article synopsis (1-2000 characters).
        contentHtml (str): Initial article HTML body.
        cefrLevel (CefrLevel): Initial target CEFR grade.
        sourceName (str | None): Origin publisher name.
        sourceUrl (str | None): Origin canonical URL.
        authorName (str | None): Article author.
        thumbnailUrl (str | None): Link to hero image.

    Example:
        >>> dto = CreateArticleDto(
        ...     categoryId=uuid.uuid4(),
        ...     title="New Discovery",
        ...     slug="new-discovery",
        ...     summary="A major breakthrough.",
        ...     contentHtml="<p>Full content.</p>",
        ...     cefrLevel=CefrLevel.B1,
        ... )
        >>> dto.slug
        'new-discovery'
    """

    categoryId: uuid.UUID
    title: str = Field(min_length=1, max_length=300)
    slug: str = Field(min_length=1, max_length=200, pattern="^[a-z0-9]+(?:-[a-z0-9]+)*$")
    summary: str = Field(min_length=1, max_length=2000)
    contentHtml: str = Field(min_length=1, max_length=1000000)
    cefrLevel: CefrLevel
    sourceName: str | None = Field(None, max_length=300)
    sourceUrl: str | None = Field(None, max_length=2048)
    authorName: str | None = Field(None, max_length=300)
    thumbnailUrl: str | None = Field(None, max_length=2048)


class UpdateArticleDto(BaseModel):
    """Payload for modifying an existing article draft.

    Attributes:
        categoryId (uuid.UUID | None): Updated category identifier.
        title (str | None): Updated headline text.
        slug (str | None): Updated URL slug.
        summary (str | None): Updated synopsis text.
        contentHtml (str | None): Updated HTML body.
        cefrLevel (CefrLevel | None): Updated CEFR rating.
        sourceName (str | None): Updated publisher name.
        sourceUrl (str | None): Updated publisher URL.
        authorName (str | None): Updated author byline.
        thumbnailUrl (str | None): Updated hero thumbnail.

    Example:
        >>> dto = UpdateArticleDto(title="Revised Title")
        >>> dto.title
        'Revised Title'
    """

    categoryId: uuid.UUID | None = None
    title: str | None = Field(None, min_length=1, max_length=300)
    slug: str | None = Field(None, min_length=1, max_length=200, pattern="^[a-z0-9]+(?:-[a-z0-9]+)*$")
    summary: str | None = Field(None, min_length=1, max_length=2000)
    contentHtml: str | None = Field(None, min_length=1, max_length=1000000)
    cefrLevel: CefrLevel | None = None
    sourceName: str | None = Field(None, max_length=300)
    sourceUrl: str | None = Field(None, max_length=2048)
    authorName: str | None = Field(None, max_length=300)
    thumbnailUrl: str | None = Field(None, max_length=2048)


class ArticleMutationDataDto(BaseModel):
    """Payload envelope returned following article draft creation.

    Attributes:
        article (AdminArticleDto): Mutated article details.

    Example:
        >>> # Returned after POST /api/v1/admin/articles
    """

    article: AdminArticleDto


class ArticleUpdateDataDto(BaseModel):
    """Payload envelope returned following article update.

    Attributes:
        article (AdminArticleDto): Updated article details.
        contentChanged (bool): Whether contentHtml was changed (invalidating sentence cache).

    Example:
        >>> # Returned after PATCH /api/v1/admin/articles/{id}
    """

    article: AdminArticleDto
    contentChanged: bool


class ParseArticleContentDto(BaseModel):
    """Request payload for triggering HTML sentence segmentation.

    Attributes:
        force (bool): Whether to overwrite preexisting sentence segmentation.

    Example:
        >>> dto = ParseArticleContentDto(force=True)
        >>> dto.force
        True
    """

    force: bool = False


class ParseArticleContentDataDto(BaseModel):
    """Response envelope following sentence segmentation.

    Attributes:
        contentVersion (int): Updated content revision version.
        sentenceCount (int): Number of created sentence spans.
        contentHtml (str): HTML string annotated with data-sentence-id spans.

    Example:
        >>> # Returned after POST /api/v1/admin/articles/{id}/parse-content
    """

    contentVersion: int
    sentenceCount: int
    contentHtml: str


class ArticleAnalysisDataDto(BaseModel):
    """Response envelope for CEFR and candidate vocabulary analysis jobs.

    Attributes:
        articleId (uuid.UUID): Target article unique identifier.
        contentVersion (int): Associated content version.
        aiAnalysisStatus (AiGenerationStatus): Readiness status of analysis.
        category (PublicCategoryDto): Associated category details.
        cefrLevel (CefrLevel): Re-evaluated CEFR readability rating.
        candidateCount (int): Number of candidate vocabulary terms detected.

    Example:
        >>> # Returned after POST /api/v1/admin/articles/{id}/analyze
    """

    articleId: uuid.UUID
    contentVersion: int
    aiAnalysisStatus: AiGenerationStatus
    category: PublicCategoryDto
    cefrLevel: CefrLevel
    candidateCount: int


class ArticlePublishDataDto(BaseModel):
    """Response envelope confirming article publication.

    Attributes:
        id (uuid.UUID): Article unique identifier.
        status (ArticleStatus): Editorial status (PUBLISHED).
        publishedAt (datetime): Timestamp of publication.

    Example:
        >>> # Returned after POST /api/v1/admin/articles/{id}/publish
    """

    id: uuid.UUID
    status: ArticleStatus
    publishedAt: datetime


class ArticleArchiveDataDto(BaseModel):
    """Response envelope confirming article archival.

    Attributes:
        id (uuid.UUID): Article unique identifier.
        status (ArticleStatus): Editorial status (ARCHIVED).
        archivedAt (datetime): Timestamp of archival.

    Example:
        >>> # Returned after POST /api/v1/admin/articles/{id}/archive
    """

    id: uuid.UUID
    status: ArticleStatus
    archivedAt: datetime


class ArticleRestoreDraftDataDto(BaseModel):
    """Response envelope confirming article restoration to draft.

    Attributes:
        id (uuid.UUID): Article unique identifier.
        status (ArticleStatus): Editorial status (DRAFT).

    Example:
        >>> # Returned after POST /api/v1/admin/articles/{id}/restore-draft
    """

    id: uuid.UUID
    status: ArticleStatus


class PublicationValidationIssueDto(BaseModel):
    """Diagnostic issue explaining why an article cannot be published.

    Attributes:
        code (str): Machine-readable issue identifier.
        message (str): Human-readable diagnostic description.
        entityId (str | None): Identifier of offending entity if applicable.

    Example:
        >>> issue = PublicationValidationIssueDto(code="NO_SENTENCES", message="Article has no sentences")
        >>> issue.code
        'NO_SENTENCES'
    """

    code: str
    message: str
    entityId: str | None = None


# ---------------------------------------------------------------------------
# Sentence & Term DTOs
# ---------------------------------------------------------------------------


class ArticleSentenceDto(CamelModel):
    """Core sentence model representing an ordered segment of article text.

    Attributes:
        id (uuid.UUID): Unique sentence identifier matching data-sentence-id.
        article_id (uuid.UUID): Parent article identifier.
        content_version (int): Content revision during segmentation.
        sentence_order (int): 1-indexed reading order within the article.
        sentence_text (str): Plain English text.
        translation_vi (str | None): Vietnamese translation.
        is_active (bool): Active visibility flag.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last modification timestamp.

    Example:
        >>> # ArticleSentenceDto represents an individual sentence
    """

    id: uuid.UUID
    article_id: uuid.UUID
    content_version: int
    sentence_order: int
    sentence_text: str
    translation_vi: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ArticleSentenceTermDto(CamelModel):
    """Contextual vocabulary term attached to an article sentence.

    Attributes:
        id (uuid.UUID): Unique term identifier matching data-term-id.
        sentence_id (uuid.UUID): Parent sentence identifier.
        value (str): Surface form in the sentence text.
        lemma (str): Dictionary canonical lemma.
        part_of_speech (str | None): Part of speech code.
        ipa (str | None): Phonetic transcription.
        cefr_level (CefrLevel | None): Lexical CEFR difficulty rating.
        contextual_meaning_vi (str | None): Vietnamese contextual meaning.
        definition_en (str | None): English definition.
        contextual_explanation (str | None): Detailed usage note.
        synonyms (list[str]): Synonyms list.
        antonyms (list[str]): Antonyms list.
        collocations (list[str]): Collocations list.
        related_terms (list[str]): Related terms list.
        examples (list[dict]): Usage examples list.
        origin (TermOrigin): Origin source (MANUAL, AI, NLP).
        review_status (TermReviewStatus): Editorial review state.
        explanation_status (AiGenerationStatus): AI enrichment readiness.
        explanation_error (str | None): AI failure message.
        is_lookup_enabled (bool): Whether lookup modal is active.
        is_active (bool): Whether term is active and highlighted.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Modification timestamp.

    Example:
        >>> # ArticleSentenceTermDto represents a vocabulary occurrence
    """

    id: uuid.UUID
    sentence_id: uuid.UUID
    value: str
    lemma: str
    part_of_speech: str | None = None
    ipa: str | None = None
    cefr_level: CefrLevel | None = None
    contextual_meaning_vi: str | None = None
    definition_en: str | None = None
    contextual_explanation: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    antonyms: list[str] = Field(default_factory=list)
    collocations: list[str] = Field(default_factory=list)
    related_terms: list[str] = Field(default_factory=list)
    examples: list[dict] = Field(default_factory=list)
    origin: TermOrigin
    review_status: TermReviewStatus
    explanation_status: AiGenerationStatus
    explanation_error: str | None = None
    is_lookup_enabled: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AdminArticleSentenceItemDto(ArticleSentenceDto):
    """Sentence summary item with aggregated term count.

    Attributes:
        term_count (int): Count of vocabulary terms linked to this sentence.

    Example:
        >>> # Sentence list item with term count
    """

    term_count: int = 0


class AdminArticleSentenceDetailDto(ArticleSentenceDto):
    """Sentence detail including list of associated contextual terms.

    Attributes:
        terms (list[ArticleSentenceTermDto]): Child vocabulary terms.

    Example:
        >>> # Loaded in admin sentence detail view
    """

    terms: list[ArticleSentenceTermDto] = Field(default_factory=list)


class UpdateArticleSentenceDto(BaseModel):
    """Request payload for updating sentence translation or active status.

    Attributes:
        translationVi (str | None): Optional Vietnamese translation text.
        isActive (bool | None): Optional visibility status flag.

    Example:
        >>> dto = UpdateArticleSentenceDto(translationVi="Bản dịch tiếng Việt.")
        >>> dto.translationVi
        'Bản dịch tiếng Việt.'
    """

    translationVi: str | None = Field(None, min_length=1, max_length=20000)
    isActive: bool | None = None


class ArticleTermExampleDto(BaseModel):
    """Contextual example sentence with Vietnamese translation.

    Attributes:
        sentence (str): English usage example sentence.
        translation (str): Vietnamese translation of example.

    Example:
        >>> ex = ArticleTermExampleDto(sentence="Example sentence.", translation="Câu ví dụ.")
        >>> ex.sentence
        'Example sentence.'
    """

    sentence: str = Field(min_length=1, max_length=2000)
    translation: str = Field(min_length=1, max_length=2000)


class CreateArticleTermDto(BaseModel):
    """Request payload for creating a contextual vocabulary term inside a sentence.

    Attributes:
        value (str): Word or expression to mark (1-500 characters).
        lemma (str): Dictionary base lemma (1-500 characters).
        partOfSpeech (str | None): Part of speech.
        ipa (str | None): Phonetic notation.
        cefrLevel (CefrLevel | None): Lexical grade.
        contextualMeaningVi (str | None): Vietnamese meaning.
        definitionEn (str | None): English definition.
        contextualExplanation (str | None): Usage note.
        synonyms (list[str]): Synonyms.
        antonyms (list[str]): Antonyms.
        collocations (list[str]): Collocations.
        relatedTerms (list[str]): Related terms.
        examples (list[dict]): Usage examples.

    Example:
        >>> dto = CreateArticleTermDto(value="quantum", lemma="quantum", cefrLevel=CefrLevel.B2)
        >>> dto.value
        'quantum'
    """

    value: str = Field(min_length=1, max_length=500)
    lemma: str = Field(min_length=1, max_length=500)
    partOfSpeech: str | None = Field(None, max_length=100)
    ipa: str | None = Field(None, max_length=200)
    cefrLevel: CefrLevel | None = None
    contextualMeaningVi: str | None = Field(None, max_length=20000)
    definitionEn: str | None = Field(None, max_length=20000)
    contextualExplanation: str | None = Field(None, max_length=20000)
    synonyms: list[str] = Field(default_factory=list)
    antonyms: list[str] = Field(default_factory=list)
    collocations: list[str] = Field(default_factory=list)
    relatedTerms: list[str] = Field(default_factory=list)
    examples: list[dict] = Field(default_factory=list)


class UpdateArticleTermDto(BaseModel):
    """Request payload for partially updating a contextual vocabulary term.

    Attributes:
        value (str | None): Optional updated surface form.
        lemma (str | None): Optional updated lemma.
        partOfSpeech (str | None): Optional updated part of speech.
        ipa (str | None): Optional updated IPA notation.
        cefrLevel (CefrLevel | None): Optional updated CEFR rating.
        contextualMeaningVi (str | None): Optional updated Vietnamese translation.
        definitionEn (str | None): Optional updated English definition.
        contextualExplanation (str | None): Optional updated usage note.
        synonyms (list[str] | None): Optional updated synonyms.
        antonyms (list[str] | None): Optional updated antonyms.
        collocations (list[str] | None): Optional updated collocations.
        relatedTerms (list[str] | None): Optional updated related terms.
        examples (list[dict] | None): Optional updated examples.
        isLookupEnabled (bool | None): Optional toggle for learner lookup capability.
        isActive (bool | None): Optional toggle for term marker active state.

    Example:
        >>> dto = UpdateArticleTermDto(contextualMeaningVi="Ý nghĩa mới.")
        >>> dto.contextualMeaningVi
        'Ý nghĩa mới.'
    """

    value: str | None = Field(None, min_length=1, max_length=500)
    lemma: str | None = Field(None, min_length=1, max_length=500)
    partOfSpeech: str | None = Field(None, max_length=100)
    ipa: str | None = Field(None, max_length=200)
    cefrLevel: CefrLevel | None = None
    contextualMeaningVi: str | None = Field(None, max_length=20000)
    definitionEn: str | None = Field(None, max_length=20000)
    contextualExplanation: str | None = Field(None, max_length=20000)
    synonyms: list[str] | None = None
    antonyms: list[str] | None = None
    collocations: list[str] | None = None
    relatedTerms: list[str] | None = None
    examples: list[dict] | None = None
    isLookupEnabled: bool | None = None
    isActive: bool | None = None


class AdminArticleTermDetailDto(ArticleSentenceTermDto):
    """Contextual term detail including parent sentence metadata.

    Attributes:
        parent_sentence (ArticleSentenceDto): Associated parent sentence record.

    Example:
        >>> # Loaded in admin term detail view
    """

    parent_sentence: ArticleSentenceDto


class ArticleTermMutationDataDto(CamelModel):
    """Response envelope data for term creation, update, and moderation actions.

    Attributes:
        term (ArticleSentenceTermDto): Mutated vocabulary term.
        content_html_changed (bool): Whether enclosing article content_html was re-rendered.

    Example:
        >>> # Returned after term mutations
    """

    term: ArticleSentenceTermDto
    content_html_changed: bool = False
