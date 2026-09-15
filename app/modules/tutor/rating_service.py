"""Authoritative FSRS rating evaluation and text normalization service for activity grading."""

from dataclasses import dataclass

from fsrs import Rating

from app.models.enums import FsrsCardState, TutorQuestionType

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SLOW_RESPONSE_MS: int = 30_000
EASY_MAX_RESPONSE_MS: int = 5_000
EASY_MIN_REVIEW_COUNT: int = 3


@dataclass
class RatingParams:
    """All inputs needed to determine the FSRS rating for one answered item.

    Attributes:
        is_correct (bool): Server-evaluated correctness boolean.
        hint_used (bool): Whether learner requested hint assistance.
        response_time_ms (int | None): Time elapsed in milliseconds before submission.
        question_type (TutorQuestionType): Question interaction format.
        fsrs_state (FsrsCardState): Memory state prior to this review.
        review_count (int): Review repetitions count prior to this review.
    """

    is_correct: bool
    hint_used: bool
    response_time_ms: int | None
    question_type: TutorQuestionType
    fsrs_state: FsrsCardState
    review_count: int


class TutorRatingService:
    """Owns the authoritative FSRS rating policy and answer normalization."""

    @staticmethod
    def map_to_fsrs_rating(params: RatingParams) -> Rating:
        """Maps deterministic answer metadata to an FSRS rating grade.

        Policy rules (in evaluation order):
        1. Wrong answer -> Rating.Again (1)
        2. Correct + hint used -> Rating.Hard (2)
        3. Correct + slow (responseTimeMs >= 30s) -> Rating.Hard (2)
        4. MULTIPLE_CHOICE correct (no hint, not slow) -> Rating.Hard (2) [ceiling]
        5. MICRO_LESSON_RETEST correct (no hint, not slow) -> Rating.Good (3) [ceiling]
        6. TYPED_RECALL correct, no hint, not slow, state=REVIEW, reviewCount>=3, responseTimeMs < 5s -> Rating.Easy (4)
        7. CONTEXTUAL_CLOZE / TYPED_RECALL correct (all others) -> Rating.Good (3)

        Args:
            params (RatingParams): Evaluated item submission parameters.

        Returns:
            Rating: FSRS rating grade (Again, Hard, Good, Easy).

        Example:
            >>> p = RatingParams(True, False, 2500, TutorQuestionType.TYPED_RECALL, FsrsCardState.REVIEW, 3)
            >>> TutorRatingService.map_to_fsrs_rating(p) == Rating.Easy
            True
        """
        if not params.is_correct:
            return Rating.Again

        is_slow = params.response_time_ms is not None and params.response_time_ms >= SLOW_RESPONSE_MS

        if params.hint_used or is_slow:
            return Rating.Hard

        match params.question_type:
            case TutorQuestionType.MULTIPLE_CHOICE:
                return Rating.Hard

            case TutorQuestionType.MICRO_LESSON_RETEST:
                return Rating.Good

            case TutorQuestionType.TYPED_RECALL:
                is_easy = (
                    params.fsrs_state == FsrsCardState.REVIEW
                    and params.review_count >= EASY_MIN_REVIEW_COUNT
                    and params.response_time_ms is not None
                    and params.response_time_ms < EASY_MAX_RESPONSE_MS
                )
                return Rating.Easy if is_easy else Rating.Good

            case TutorQuestionType.CONTEXTUAL_CLOZE:
                return Rating.Good

            case _:
                return Rating.Good

    @staticmethod
    def normalize_typed_answer(raw: str) -> str:
        """Normalizes a typed answer string for deterministic comparison.

        Rules:
        Trims leading and trailing whitespace, then converts to lowercase.

        Args:
            raw (str): Raw string submitted by learner.

        Returns:
            str: Trimmed and lowercased string.

        Example:
            >>> TutorRatingService.normalize_typed_answer("  Apple  ")
            'apple'
        """
        return raw.strip().lower()
