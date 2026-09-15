"""Domain enumerations for the Vocab Mate learning platform."""

import enum


class UserRole(str, enum.Enum):
    """User authorization roles within the application."""

    ADMIN = "ADMIN"
    USER = "USER"


class UserStatus(str, enum.Enum):
    """Lifecycle and access state of a user account."""

    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DISABLED = "DISABLED"


class CefrLevel(str, enum.Enum):
    """Common European Framework of Reference for Languages (CEFR) levels."""

    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"


class ArticleStatus(str, enum.Enum):
    """Publication lifecycle status of an article."""

    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class AiGenerationStatus(str, enum.Enum):
    """Processing state for background AI generation and enrichment jobs."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


class TermOrigin(str, enum.Enum):
    """Origin source of a vocabulary term occurrence."""

    MANUAL = "MANUAL"
    AI = "AI"
    NLP = "NLP"


class TermReviewStatus(str, enum.Enum):
    """Editorial curation status of a vocabulary term."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ReadingStatus(str, enum.Enum):
    """Learner reading progress status on an article."""

    READING = "READING"
    COMPLETED = "COMPLETED"


class FsrsCardState(str, enum.Enum):
    """Spaced repetition memory state according to the FSRS algorithm."""

    NEW = "NEW"
    LEARNING = "LEARNING"
    REVIEW = "REVIEW"
    RELEARNING = "RELEARNING"


class TutorSessionStatus(str, enum.Enum):
    """Daily tutor review session progress state."""

    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"


class TutorSessionItemStatus(str, enum.Enum):
    """Completion state of an individual question item within a tutor session."""

    PENDING = "PENDING"
    ANSWERED = "ANSWERED"
    SKIPPED = "SKIPPED"


class TutorQuestionType(str, enum.Enum):
    """Interaction format for AI-generated vocabulary practice questions."""

    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"
    CONTEXTUAL_CLOZE = "CONTEXTUAL_CLOZE"
    TYPED_RECALL = "TYPED_RECALL"
    MICRO_LESSON_RETEST = "MICRO_LESSON_RETEST"
