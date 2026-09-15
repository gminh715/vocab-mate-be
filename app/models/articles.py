"""SQLAlchemy ORM models representing articles, parsed sentences, and contextual terms."""

import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    func,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import (
    AiGenerationStatus,
    ArticleStatus,
    CefrLevel,
    TermOrigin,
    TermReviewStatus,
)


class Article(Base):
    """Article entity matching PostgreSQL 'articles' table.

    Attributes:
        id (uuid.UUID): Primary key UUID identifier.
        category_id (uuid.UUID): Foreign key reference to Category ID.
        title (str): Article headline title.
        slug (str): Unique URL-friendly slug identifier.
        summary (str): Short summary synopsis.
        content_html (str): Sanitized HTML body containing sentence and term markers.
        content_version (int): Incremental content version number.
        source_name (str | None): Original publishing outlet name.
        source_url (str | None): Original source article URL.
        author_name (str | None): Journalist or author attribution.
        thumbnail_url (str | None): Hosted cover image URL.
        external_id (str | None): External platform or feed identifier.
        source_published_at (datetime | None): Timestamp of original publishing.
        ai_analysis_status (AiGenerationStatus | None): Background NLP analysis state.
        ai_analysis_error (str | None): Explanatory error message if analysis failed.
        cefr_level (CefrLevel): Overall article CEFR complexity grade (A1-C2).
        status (ArticleStatus): Editorial publication lifecycle state.
        published_at (datetime | None): Timestamp when article was published.
        archived_at (datetime | None): Timestamp when article was archived.
        created_at (datetime): Database record insertion timestamp.
        updated_at (datetime): Last modification timestamp.
    """

    __tablename__ = "articles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    category_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    content_html: Mapped[str] = mapped_column(Text, nullable=False)
    content_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    source_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    author_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ai_analysis_status: Mapped[AiGenerationStatus | None] = mapped_column(
        SQLEnum(AiGenerationStatus, name="ai_generation_status", create_type=False),
        nullable=True,
    )
    ai_analysis_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    cefr_level: Mapped[CefrLevel] = mapped_column(
        SQLEnum(CefrLevel, name="cefr_level", create_type=False),
        nullable=False,
    )
    status: Mapped[ArticleStatus] = mapped_column(
        SQLEnum(ArticleStatus, name="article_status", create_type=False),
        default=ArticleStatus.DRAFT,
        nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    category = relationship("Category", back_populates="articles")
    sentences = relationship("ArticleSentence", back_populates="article", cascade="all, delete-orphan")
    reader_progress = relationship("UserArticleProgress", back_populates="article")


class ArticleSentence(Base):
    """Parsed sentence unit from article content.

    Attributes:
        id (uuid.UUID): Primary key UUID identifier.
        article_id (uuid.UUID): Foreign key reference to parent Article ID.
        content_version (int): Content version snapshot number.
        sentence_order (int): 1-indexed sequential position within article.
        sentence_text (str): Raw plain text of sentence.
        translation_vi (str | None): Vietnamese sentence translation.
        is_active (bool): Active visibility state.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
    """

    __tablename__ = "article_sentences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    content_version: Mapped[int] = mapped_column(Integer, nullable=False)
    sentence_order: Mapped[int] = mapped_column(Integer, nullable=False)
    sentence_text: Mapped[str] = mapped_column(Text, nullable=False)
    translation_vi: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    article = relationship("Article", back_populates="sentences")
    terms = relationship("ArticleSentenceTerm", back_populates="sentence", cascade="all, delete-orphan")


class ArticleSentenceTerm(Base):
    """Vocabulary term occurrence inside an article sentence.

    Attributes:
        id (uuid.UUID): Primary key UUID identifier.
        sentence_id (uuid.UUID): Foreign key reference to parent ArticleSentence ID.
        value (str): Surface form as it appears in the sentence.
        lemma (str): Normalized base dictionary form.
        part_of_speech (str | None): Grammatical tag.
        ipa (str | None): International Phonetic Alphabet pronunciation.
        cefr_level (CefrLevel | None): CEFR difficulty level.
        contextual_meaning_vi (str | None): Vietnamese contextual definition.
        definition_en (str | None): English dictionary definition.
        contextual_explanation (str | None): In-depth usage explanation.
        synonyms (list[str]): Synonymous vocabulary words.
        antonyms (list[str]): Antonymic vocabulary words.
        collocations (list[str]): Frequent word pairings.
        related_terms (list[str]): Related topical terms.
        examples (list[dict]): Contextual example usages.
        origin (TermOrigin): Source of term identification (MANUAL, AI, NLP).
        review_status (TermReviewStatus): Editorial status (PENDING, APPROVED, REJECTED).
        explanation_status (AiGenerationStatus): AI enrichment generation state.
        explanation_error (str | None): AI enrichment failure details.
        is_lookup_enabled (bool): Whether term lookup is enabled in reader.
        is_active (bool): Whether term is active and highlighted.
        created_at (datetime): Insertion timestamp.
        updated_at (datetime): Last update timestamp.
    """

    __tablename__ = "article_sentence_terms"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    sentence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("article_sentences.id", ondelete="CASCADE"), nullable=False
    )
    value: Mapped[str] = mapped_column(Text, nullable=False)
    lemma: Mapped[str] = mapped_column(Text, nullable=False)
    part_of_speech: Mapped[str | None] = mapped_column(Text, nullable=True)
    ipa: Mapped[str | None] = mapped_column(Text, nullable=True)
    cefr_level: Mapped[CefrLevel | None] = mapped_column(
        SQLEnum(CefrLevel, name="cefr_level", create_type=False),
        nullable=True,
    )
    contextual_meaning_vi: Mapped[str | None] = mapped_column(Text, nullable=True)
    definition_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    contextual_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    synonyms: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    antonyms: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    collocations: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    related_terms: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    examples: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False)
    origin: Mapped[TermOrigin] = mapped_column(
        SQLEnum(TermOrigin, name="term_origin", create_type=False),
        default=TermOrigin.MANUAL,
        nullable=False,
    )
    review_status: Mapped[TermReviewStatus] = mapped_column(
        SQLEnum(TermReviewStatus, name="term_review_status", create_type=False),
        default=TermReviewStatus.APPROVED,
        nullable=False,
    )
    explanation_status: Mapped[AiGenerationStatus] = mapped_column(
        SQLEnum(AiGenerationStatus, name="ai_generation_status", create_type=False),
        default=AiGenerationStatus.READY,
        nullable=False,
    )
    explanation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_lookup_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    sentence = relationship("ArticleSentence", back_populates="terms")
    user_vocabularies = relationship("UserVocabulary", back_populates="article_sentence_term")
