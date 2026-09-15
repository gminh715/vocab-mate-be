"""SQLAlchemy ORM model representing user-saved contextual vocabularies and FSRS states."""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Text,
    func,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import CefrLevel, FsrsCardState


class UserVocabulary(Base):
    """User-saved vocabulary item with FSRS flashcard state.

    Attributes:
        id (uuid.UUID): Primary key UUID identifier.
        user_id (uuid.UUID): Foreign key reference to User ID.
        article_sentence_term_id (uuid.UUID): Foreign key reference to ArticleSentenceTerm ID.
        saved_word_display (str): Display text captured at save time.
        saved_lemma (str): Normalized dictionary lemma.
        saved_part_of_speech (str): Word grammatical category.
        saved_ipa (str | None): Phonetic transcription.
        saved_cefr_level (CefrLevel): CEFR level of term at save time.
        saved_meaning_vi (str): Vietnamese contextual translation.
        definition_en (str | None): English definition.
        saved_examples (list[dict]): Examples snapshot.
        saved_at (datetime): Timestamp when user saved this vocabulary item.
        created_at (datetime): Database insertion timestamp.
        updated_at (datetime): Last modification timestamp.
        fsrs_state (FsrsCardState): Memory state (NEW, LEARNING, REVIEW, RELEARNING).
        fsrs_stability (float | None): Memory stability factor S.
        fsrs_difficulty (float | None): Memory difficulty factor D (1.0 to 10.0).
        fsrs_scheduled_days (int): Interval in days to next scheduled review.
        fsrs_learning_steps (int): Step count in initial learning phase.
        review_count (int): Total number of review repetitions.
        lapse_count (int): Total times rating was Again after learning.
        last_reviewed_at (datetime | None): Timestamp of last tutor review.
        next_review_at (datetime | None): Timestamp when item is due for next review.
    """

    __tablename__ = "user_vocabularies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    article_sentence_term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("article_sentence_terms.id"), nullable=False, index=True
    )
    saved_word_display: Mapped[str] = mapped_column(Text, nullable=False)
    saved_lemma: Mapped[str] = mapped_column(Text, nullable=False)
    saved_part_of_speech: Mapped[str] = mapped_column(Text, nullable=False)
    saved_ipa: Mapped[str | None] = mapped_column(Text, nullable=True)
    saved_cefr_level: Mapped[CefrLevel] = mapped_column(
        SQLEnum(CefrLevel, name="cefr_level", create_type=False),
        nullable=False,
    )
    saved_meaning_vi: Mapped[str] = mapped_column(Text, nullable=False)
    definition_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    saved_examples: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False)
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # FSRS scheduling fields
    fsrs_state: Mapped[FsrsCardState] = mapped_column(
        SQLEnum(FsrsCardState, name="fsrs_card_state", create_type=False),
        default=FsrsCardState.NEW,
        nullable=False,
    )
    fsrs_stability: Mapped[float | None] = mapped_column(Float, nullable=True)
    fsrs_difficulty: Mapped[float | None] = mapped_column(Float, nullable=True)
    fsrs_scheduled_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fsrs_learning_steps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lapse_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="vocabularies")
    article_sentence_term = relationship("ArticleSentenceTerm", back_populates="user_vocabularies")
    collection_items = relationship(
        "VocabularyCollectionItem", back_populates="user_vocabulary", cascade="all, delete-orphan"
    )
    tutor_session_items = relationship("TutorSessionItem", back_populates="user_vocabulary")
