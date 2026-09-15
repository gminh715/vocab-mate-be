"""Pydantic schemas and DTOs for the Tutor session and FSRS learning module."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TutorQuestionType, TutorSessionItemStatus, TutorSessionStatus

# ---------------------------------------------------------------------------
# Rating distribution DTO
# ---------------------------------------------------------------------------


class RatingDistributionDto(BaseModel):
    """Breakdown of assigned FSRS ratings across the four grade levels.

    Attributes:
        again (int): Count of Again (1) ratings.
        hard (int): Count of Hard (2) ratings.
        good (int): Count of Good (3) ratings.
        easy (int): Count of Easy (4) ratings.
    """

    again: int = Field(default=0, ge=0, description="Count of Again (1) ratings")
    hard: int = Field(default=0, ge=0, description="Count of Hard (2) ratings")
    good: int = Field(default=0, ge=0, description="Count of Good (3) ratings")
    easy: int = Field(default=0, ge=0, description="Count of Easy (4) ratings")


# ---------------------------------------------------------------------------
# Summary statistics DTO
# ---------------------------------------------------------------------------


class TutorSessionSummaryStatsDto(BaseModel):
    """Performance and pacing statistics for a completed or abandoned tutor session.

    Attributes:
        durationSeconds (int): Actual session duration in seconds.
        plannedActivities (int): Target activity count planned for the session.
        completedActivities (int): Actual number of activities completed.
        correctCount (int): Count of correct answers.
        incorrectCount (int): Count of incorrect answers.
        newWordsStudied (int): Number of NEW words studied.
        reviewWordsStudied (int): Number of review/learning words studied.
        ratingDistribution (RatingDistributionDto): Distribution of FSRS ratings assigned.
        relearningWords (list[str]): Words that lapsed or entered relearning during this session.
        nextDueCount (int): Total vocabulary items currently due for review after this session.
    """

    durationSeconds: int = Field(ge=0, description="Actual session duration in seconds")
    plannedActivities: int = Field(ge=1, description="Target activity count planned for the session")
    completedActivities: int = Field(ge=0, description="Actual number of activities completed")
    correctCount: int = Field(ge=0, description="Count of correct answers")
    incorrectCount: int = Field(ge=0, description="Count of incorrect answers")
    newWordsStudied: int = Field(ge=0, description="Number of NEW words studied")
    reviewWordsStudied: int = Field(ge=0, description="Number of review/learning words studied")
    ratingDistribution: RatingDistributionDto = Field(description="Distribution of FSRS ratings assigned")
    relearningWords: list[str] = Field(
        default_factory=list, description="Words that lapsed or entered relearning during this session"
    )
    nextDueCount: int = Field(ge=0, description="Total vocabulary items currently due for review after this session")


# ---------------------------------------------------------------------------
# Session Summary DTO
# ---------------------------------------------------------------------------


class TutorSessionSummaryDto(BaseModel):
    """Public metadata snapshot of a daily tutor session.

    Attributes:
        id (uuid.UUID): Unique session identifier.
        userId (uuid.UUID): Identifier of owning user.
        studyDate (str): Calendar study date string (YYYY-MM-DD) in Asia/Ho_Chi_Minh timezone.
        status (TutorSessionStatus): Session lifecycle state (ACTIVE, COMPLETED, ABANDONED).
        targetDurationMinutes (int): Target session duration in minutes.
        targetActivityCount (int): Target total activity count for the session.
        newWordTarget (int): Target number of NEW words to introduce.
        startedAt (datetime): Session initiation timestamp.
        completedAt (datetime | None): Session completion timestamp.
        warmupFacts (Any | None): Optional pre-test warmup fact stories.
        createdAt (datetime): Database insertion timestamp.
        updatedAt (datetime): Last modification timestamp.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    userId: uuid.UUID
    studyDate: str
    status: TutorSessionStatus
    targetDurationMinutes: int
    targetActivityCount: int
    newWordTarget: int
    startedAt: datetime
    completedAt: datetime | None = None
    warmupFacts: Any | None = None
    createdAt: datetime
    updatedAt: datetime


# ---------------------------------------------------------------------------
# Activity Item DTOs
# ---------------------------------------------------------------------------


class TutorSessionPendingItemDto(BaseModel):
    """Public activity item payload served to learners before answering.

    Attributes:
        id (uuid.UUID): Unique activity item identifier.
        sessionId (uuid.UUID): Identifier of parent tutor session.
        userVocabularyId (uuid.UUID | None): Associated UserVocabulary ID (null if deleted).
        position (int): 1-based sequential position within the session.
        status (TutorSessionItemStatus): Question status (PENDING, ANSWERED, SKIPPED).
        questionType (TutorQuestionType): Interaction format (e.g. MULTIPLE_CHOICE).
        isNewWord (bool): Whether this activity is for a NEW word.
        questionPayload: Public activity payload rendered by frontend.
        hintUsed (bool): Whether the user requested a hint.
        generatedAt (datetime): Item generation timestamp.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sessionId: uuid.UUID
    userVocabularyId: uuid.UUID | None = None
    position: int
    status: TutorSessionItemStatus
    questionType: TutorQuestionType
    isNewWord: bool
    questionPayload: dict[str, Any]
    hintUsed: bool = False
    generatedAt: datetime


class TutorSessionAnsweredItemDto(TutorSessionPendingItemDto):
    """Completed activity item payload revealing grading result, canonical answer, and explanation.

    Attributes:
        userAnswer (Any | None): Learner submitted answer.
        isCorrect (bool | None): Server-evaluated correctness boolean.
        responseTimeMs (int | None): Response time in milliseconds.
        fsrsRating (int | None): Assigned FSRS rating (1=Again, 2=Hard, 3=Good, 4=Easy).
        feedbackVi (str | None): Contextual feedback in Vietnamese.
        correctAnswer (Any | None): Canonical correct answer.
        explanationVi (str | None): Detailed pedagogical explanation in Vietnamese.
        answeredAt (datetime | None): Timestamp when answer was submitted.
    """

    userAnswer: Any | None = None
    isCorrect: bool | None = None
    responseTimeMs: int | None = None
    fsrsRating: int | None = None
    feedbackVi: str | None = None
    correctAnswer: Any | None = None
    explanationVi: str | None = None
    answeredAt: datetime | None = None


# ---------------------------------------------------------------------------
# Today Status DTOs
# ---------------------------------------------------------------------------


class TodayStatusDataDto(BaseModel):
    """Readiness state and status summary for today's daily tutor session.

    Attributes:
        canStart (bool): Whether the user is eligible to start a new tutor session today.
        canResume (bool): Whether there is an active session today that can be resumed.
        isCompletedToday (bool): Whether the user has already completed their daily session today.
        isAbandoned (bool): Whether today's session was abandoned.
        dueCount (int): Number of vocabulary items currently due for review.
        session (TutorSessionSummaryDto | None): Today session summary if one exists, otherwise None.
    """

    canStart: bool
    canResume: bool
    isCompletedToday: bool
    isAbandoned: bool
    dueCount: int
    session: TutorSessionSummaryDto | None = None


# ---------------------------------------------------------------------------
# Session State and Detail DTOs
# ---------------------------------------------------------------------------


class TutorSessionWithItemDataDto(BaseModel):
    """Active tutor session response containing session summary, pending item, or final stats.

    Attributes:
        session (TutorSessionSummaryDto): Public session metadata summary.
        currentItem (TutorSessionPendingItemDto | None): The current PENDING question to be answered.
        summary (TutorSessionSummaryStatsDto | None): Session summary stats when finished.
    """

    session: TutorSessionSummaryDto
    currentItem: TutorSessionPendingItemDto | None = None
    summary: TutorSessionSummaryStatsDto | None = None


class TutorSessionDetailDataDto(BaseModel):
    """Comprehensive session review payload including full question history and summary stats.

    Attributes:
        session (TutorSessionSummaryDto): Public session metadata summary.
        items (list[TutorSessionAnsweredItemDto]): All items in the session in sequential order.
        summary (TutorSessionSummaryStatsDto | None): Summary statistics for this session.
    """

    session: TutorSessionSummaryDto
    items: list[TutorSessionAnsweredItemDto]
    summary: TutorSessionSummaryStatsDto | None = None


# ---------------------------------------------------------------------------
# Submit Answer DTOs
# ---------------------------------------------------------------------------


class SubmitAnswerDto(BaseModel):
    """Client payload for submitting an answer to an active activity item.

    Attributes:
        answer (Any): User response (option ID for MC, text string for CLOZE/TYPED_RECALL).
        hintUsed (bool): Whether the learner opened/viewed the hint for this question.
        responseTimeMs (int | None): Time elapsed in milliseconds before submission.
    """

    answer: Any
    hintUsed: bool = False
    responseTimeMs: int | None = Field(default=None, ge=0, le=600_000)


class SubmitAnswerResponseDataDto(BaseModel):
    """Result payload returned upon submitting an activity item answer.

    Attributes:
        item (TutorSessionAnsweredItemDto): The answered item with grading result.
        sessionStatus (TutorSessionStatus): Updated session status (ACTIVE or COMPLETED).
        isSessionCompleted (bool): True if this submission completed the target activity quota.
    """

    item: TutorSessionAnsweredItemDto
    sessionStatus: TutorSessionStatus
    isSessionCompleted: bool


# ---------------------------------------------------------------------------
# History Query and Data DTOs
# ---------------------------------------------------------------------------


class TutorHistoryQueryDto(BaseModel):
    """Query parameters for cursor-based keyset pagination of tutor session history.

    Attributes:
        cursor (str | None): Opaque Base64 cursor string for keyset pagination.
        limit (int): Number of sessions to retrieve per page (1 to 50, default 20).
    """

    cursor: str | None = None
    limit: int = Field(default=20, ge=1, le=50)


class TutorHistoryDataDto(BaseModel):
    """Data payload containing a paginated slice of historical tutor sessions.

    Attributes:
        items (list[TutorSessionSummaryDto]): Paginated list of completed/historical sessions.
        nextCursor (str | None): Next cursor for fetching the following page, or None.
        hasMore (bool): True if more historical sessions remain after this page.
    """

    items: list[TutorSessionSummaryDto]
    nextCursor: str | None = None
    hasMore: bool
