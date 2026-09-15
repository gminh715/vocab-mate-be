"""Authoritative FSRS calculation and scheduling service for the vocabulary tutor."""

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fsrs import Card, Rating, Scheduler, State

from app.core.config import settings
from app.models.enums import FsrsCardState

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SECONDS_PER_ACTIVITY: int = 45
MIN_ACTIVITY_COUNT: int = 3
MAX_ACTIVITY_COUNT: int = 40
NEW_WORD_RATIO: float = 0.2
REQUEST_RETENTION: float = 0.9

# ---------------------------------------------------------------------------
# State mapping helpers
# ---------------------------------------------------------------------------

FSRS_STATE_TO_TS: dict[FsrsCardState, State] = {
    FsrsCardState.NEW: State.Learning,
    FsrsCardState.LEARNING: State.Learning,
    FsrsCardState.REVIEW: State.Review,
    FsrsCardState.RELEARNING: State.Relearning,
}

TS_STATE_TO_FSRS: dict[State, FsrsCardState] = {
    State.Learning: FsrsCardState.LEARNING,
    State.Review: FsrsCardState.REVIEW,
    State.Relearning: FsrsCardState.RELEARNING,
}


@dataclass
class FsrsCardFields:
    """Fields from UserVocabulary needed to reconstruct an FSRS card.

    Attributes:
        fsrs_state (FsrsCardState): Memory state in database.
        fsrs_stability (float | None): Memory stability factor S.
        fsrs_difficulty (float | None): Memory difficulty factor D.
        fsrs_scheduled_days (int): Interval in days to next review.
        fsrs_learning_steps (int): Step count in initial learning phase.
        review_count (int): Total review repetitions count.
        lapse_count (int): Total lapses count.
        next_review_at (datetime | None): Timestamp of next scheduled review.
        last_reviewed_at (datetime | None): Timestamp of last review.
    """

    fsrs_state: FsrsCardState
    fsrs_stability: float | None
    fsrs_difficulty: float | None
    fsrs_scheduled_days: int
    fsrs_learning_steps: int
    review_count: int
    lapse_count: int
    next_review_at: datetime | None
    last_reviewed_at: datetime | None


@dataclass
class UserVocabularyFsrsUpdate:
    """Fields to update on UserVocabulary after FSRS scheduling.

    Attributes:
        fsrs_state (FsrsCardState): Updated memory state.
        fsrs_stability (float): Updated memory stability.
        fsrs_difficulty (float): Updated memory difficulty.
        fsrs_scheduled_days (int): Days to next review.
        fsrs_learning_steps (int): Updated learning steps count.
        review_count (int): Incremented review repetitions count.
        lapse_count (int): Incremented lapse count if rating was Again.
        next_review_at (datetime): Target timestamp for next review.
        last_reviewed_at (datetime): Timestamp when this review was evaluated.
    """

    fsrs_state: FsrsCardState
    fsrs_stability: float
    fsrs_difficulty: float
    fsrs_scheduled_days: int
    fsrs_learning_steps: int
    review_count: int
    lapse_count: int
    next_review_at: datetime
    last_reviewed_at: datetime

    def to_dict(self) -> dict[str, Any]:
        """Converts dataclass to a dictionary for SQLAlchemy update expressions.

        Returns:
            dict[str, Any]: Mapping of UserVocabulary column names to updated values.

        Example:
            >>> # d = snapshot.to_dict()
        """
        return {
            "fsrs_state": self.fsrs_state,
            "fsrs_stability": self.fsrs_stability,
            "fsrs_difficulty": self.fsrs_difficulty,
            "fsrs_scheduled_days": self.fsrs_scheduled_days,
            "fsrs_learning_steps": self.fsrs_learning_steps,
            "review_count": self.review_count,
            "lapse_count": self.lapse_count,
            "next_review_at": self.next_review_at,
            "last_reviewed_at": self.last_reviewed_at,
        }


@dataclass
class SchedulingResult:
    """Result of scheduling a card with an FSRS grade rating.

    Attributes:
        card (Card): Updated card instance.
        rating (Rating): Applied review grade rating.
    """

    card: Card
    rating: Rating


@dataclass
class SessionTargets:
    """Session budget targets computed from user preference.

    Attributes:
        target_activity_count (int): Total questions planned for session.
        new_word_target (int): Target number of NEW words to introduce.
    """

    target_activity_count: int
    new_word_target: int


class TutorFsrsService:
    """Authoritative FSRS calculation and scheduling service for the vocabulary tutor."""

    def __init__(self, desired_retention: float = REQUEST_RETENTION) -> None:
        """Initializes the FSRS scheduler.

        Args:
            desired_retention (float, optional): Target retention rate. Defaults to 0.9.

        Example:
            >>> service = TutorFsrsService(0.9)
        """
        self.scheduler = Scheduler(desired_retention=desired_retention, enable_fuzzing=False)

    @staticmethod
    def get_study_date(now: datetime | None = None) -> str:
        """Returns the study date string (YYYY-MM-DD) for a given instant in the configured timezone.

        Args:
            now (datetime | None, optional): Instant to evaluate. Defaults to current time.

        Returns:
            str: Study date string formatted as YYYY-MM-DD.

        Example:
            >>> s = TutorFsrsService.get_study_date()
            >>> len(s)
            10
        """
        try:
            tz = ZoneInfo(settings.ANALYTICS_TIMEZONE)
        except ZoneInfoNotFoundError:
            # Fallback to +07:00 if timezone name not found in environment
            from datetime import timezone

            tz = timezone(timedelta(hours=7))

        if now is None:
            local_dt = datetime.now(tz)
        elif now.tzinfo is None:
            local_dt = now.replace(tzinfo=UTC).astimezone(tz)
        else:
            local_dt = now.astimezone(tz)

        return local_dt.strftime("%Y-%m-%d")

    @classmethod
    def build_fsrs_card(cls, fields: FsrsCardFields) -> Card:
        """Reconstructs a PyFSRS Card from UserVocabulary database entity fields.

        Args:
            fields (FsrsCardFields): Extracted UserVocabulary FSRS columns.

        Returns:
            Card: PyFSRS Card entity ready for review scheduling.

        Example:
            >>> f = FsrsCardFields(FsrsCardState.NEW, None, None, 0, 0, 0, 0, None, None)
            >>> c = TutorFsrsService.build_fsrs_card(f)
            >>> c.step
            0
        """
        if fields.fsrs_state == FsrsCardState.NEW and fields.review_count == 0:
            return Card()

        fsrs_state = FSRS_STATE_TO_TS.get(fields.fsrs_state, State.Learning)
        due_date = fields.next_review_at or datetime.now(UTC)
        if due_date.tzinfo is None:
            due_date = due_date.replace(tzinfo=UTC)

        last_review = fields.last_reviewed_at
        if last_review and last_review.tzinfo is None:
            last_review = last_review.replace(tzinfo=UTC)

        return Card(
            state=fsrs_state,
            step=fields.fsrs_learning_steps,
            stability=fields.fsrs_stability,
            difficulty=fields.fsrs_difficulty,
            due=due_date,
            last_review=last_review,
        )

    def schedule_fsrs_card(
        self,
        card: Card,
        rating: Rating,
        now: datetime | None = None,
    ) -> SchedulingResult:
        """Runs the FSRS scheduler for the given card and rating grade.

        Args:
            card (Card): Current flashcard state.
            rating (Rating): Assigned grade rating (Again, Hard, Good, Easy).
            now (datetime | None, optional): Evaluation timestamp. Defaults to UTC now.

        Returns:
            SchedulingResult: Evaluated card and rating.

        Example:
            >>> svc = TutorFsrsService()
            >>> res = svc.schedule_fsrs_card(Card(), Rating.Good)
            >>> res.rating == Rating.Good
            True
        """
        eval_now = now or datetime.now(UTC)
        if eval_now.tzinfo is None:
            eval_now = eval_now.replace(tzinfo=UTC)

        scheduled_card, _ = self.scheduler.review_card(card, rating, eval_now)
        return SchedulingResult(card=scheduled_card, rating=rating)

    @classmethod
    def map_card_to_update(
        cls,
        result: SchedulingResult,
        reviewed_at: datetime,
        current_review_count: int,
        current_lapse_count: int,
    ) -> UserVocabularyFsrsUpdate:
        """Maps an FSRS scheduling result to an update dataclass for UserVocabulary.

        Args:
            result (SchedulingResult): Evaluated scheduling result.
            reviewed_at (datetime): Evaluation timestamp.
            current_review_count (int): Previous repetitions count.
            current_lapse_count (int): Previous lapse count.

        Returns:
            UserVocabularyFsrsUpdate: Updated database entity values.

        Example:
            >>> svc = TutorFsrsService()
            >>> r = svc.schedule_fsrs_card(Card(), Rating.Good)
            >>> upd = TutorFsrsService.map_card_to_update(r, datetime.now(UTC), 0, 0)
            >>> upd.review_count
            1
        """
        card = result.card
        if reviewed_at.tzinfo is None:
            reviewed_at = reviewed_at.replace(tzinfo=UTC)

        due_date = card.due
        if due_date.tzinfo is None:
            due_date = due_date.replace(tzinfo=UTC)

        new_review_count = current_review_count + 1
        new_lapse_count = current_lapse_count + (1 if result.rating == Rating.Again else 0)

        scheduled_days = max(0, (due_date.date() - reviewed_at.date()).days)
        mapped_state = TS_STATE_TO_FSRS.get(card.state, FsrsCardState.LEARNING)

        return UserVocabularyFsrsUpdate(
            fsrs_state=mapped_state,
            fsrs_stability=card.stability or 0.0,
            fsrs_difficulty=card.difficulty or 0.0,
            fsrs_scheduled_days=scheduled_days,
            fsrs_learning_steps=card.step,
            review_count=new_review_count,
            lapse_count=new_lapse_count,
            next_review_at=due_date,
            last_reviewed_at=reviewed_at,
        )

    @staticmethod
    def calc_session_targets(
        daily_study_minutes: int,
        new_vocab_count: int,
    ) -> SessionTargets:
        """Computes session target activity count and new word target quota.

        Args:
            daily_study_minutes (int): User preferred study duration in minutes.
            new_vocab_count (int): Number of unreviewed NEW vocabulary items available.

        Returns:
            SessionTargets: Target activity count and new word target quota.

        Example:
            >>> t = TutorFsrsService.calc_session_targets(10, 5)
            >>> t.target_activity_count
            13
            >>> t.new_word_target
            3
        """
        raw = math.floor((daily_study_minutes * 60) / SECONDS_PER_ACTIVITY)
        target_activity_count = max(MIN_ACTIVITY_COUNT, min(MAX_ACTIVITY_COUNT, raw))

        if new_vocab_count > 0:
            new_word_target = max(1, math.ceil(target_activity_count * NEW_WORD_RATIO))
        else:
            new_word_target = 0

        return SessionTargets(
            target_activity_count=target_activity_count,
            new_word_target=new_word_target,
        )
