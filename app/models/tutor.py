"""SQLAlchemy ORM models representing AI tutor learning sessions and activity items."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
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
from app.models.enums import (
    TutorQuestionType,
    TutorSessionItemStatus,
    TutorSessionStatus,
)


class TutorSession(Base):
    """Daily tutor session record.

    Attributes:
        id (uuid.UUID): Primary key UUID identifier.
        user_id (uuid.UUID): Foreign key reference to User ID.
        study_date (date): Calendar date of the study session.
        status (TutorSessionStatus): Session lifecycle state (ACTIVE, COMPLETED, ABANDONED).
        target_duration_minutes (int): Allocated daily study time in minutes.
        target_activity_count (int): Target number of quiz questions.
        new_word_target (int): Target number of new vocabulary words to introduce.
        warmup_facts (list[dict] | None): Generated contextual warmup story items.
        started_at (datetime): Session initiation timestamp.
        completed_at (datetime | None): Session completion timestamp.
        created_at (datetime): Database insertion timestamp.
        updated_at (datetime): Last modification timestamp.
    """

    __tablename__ = "tutor_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    study_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[TutorSessionStatus] = mapped_column(
        SQLEnum(TutorSessionStatus, name="tutor_session_status", create_type=False),
        default=TutorSessionStatus.ACTIVE,
        nullable=False,
    )
    target_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    target_activity_count: Mapped[int] = mapped_column(Integer, nullable=False)
    new_word_target: Mapped[int] = mapped_column(Integer, nullable=False)
    warmup_facts: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="tutor_sessions")
    items = relationship("TutorSessionItem", back_populates="session", cascade="all, delete-orphan")


class TutorSessionItem(Base):
    """Single question or activity inside a tutor session.

    Attributes:
        id (uuid.UUID): Primary key UUID identifier.
        session_id (uuid.UUID): Foreign key reference to parent TutorSession ID.
        user_vocabulary_id (uuid.UUID | None): Foreign key reference to UserVocabulary.
        position (int): 1-indexed sequential position in session.
        status (TutorSessionItemStatus): Question status (PENDING, ANSWERED, SKIPPED).
        question_type (TutorQuestionType): Interaction format (e.g. MULTIPLE_CHOICE).
        is_new_word (bool): True if newly introduced word, False if review.
        question_payload (dict): Structured question definition for the client.
        grading_spec (dict): Server-side grading criteria and correct answer key.
        user_answer (dict | None): Submitted learner response.
        is_correct (bool | None): Server-evaluated correctness boolean.
        hint_used (bool): Whether learner requested hint assistance.
        response_time_ms (int | None): Time elapsed in milliseconds before submission.
        fsrs_rating (int | None): FSRS grade rating (1=Again, 2=Hard, 3=Good, 4=Easy).
        feedback_vi (str | None): AI-generated explanation feedback in Vietnamese.
        generated_at (datetime): Question generation timestamp.
        answered_at (datetime | None): Answer submission timestamp.
    """

    __tablename__ = "tutor_session_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tutor_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_vocabulary_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_vocabularies.id", ondelete="SET NULL"), nullable=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[TutorSessionItemStatus] = mapped_column(
        SQLEnum(TutorSessionItemStatus, name="tutor_session_item_status", create_type=False),
        default=TutorSessionItemStatus.PENDING,
        nullable=False,
    )
    question_type: Mapped[TutorQuestionType] = mapped_column(
        SQLEnum(TutorQuestionType, name="tutor_question_type", create_type=False),
        nullable=False,
    )
    is_new_word: Mapped[bool] = mapped_column(Boolean, nullable=False)
    question_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    grading_spec: Mapped[dict] = mapped_column(JSONB, nullable=False)
    user_answer: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    hint_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fsrs_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback_vi: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session = relationship("TutorSession", back_populates="items")
    user_vocabulary = relationship("UserVocabulary", back_populates="tutor_session_items")
