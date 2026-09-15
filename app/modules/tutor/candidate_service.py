"""Candidate vocabulary selection service for FSRS tutor session activities."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import CefrLevel, FsrsCardState
from app.models.vocabularies import UserVocabulary

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CANDIDATE_POOL_LIMIT: int = 50


@dataclass
class CandidateVocab:
    """Minimal fields of UserVocabulary returned from candidate pool queries.

    Attributes:
        id (uuid.UUID): UserVocabulary unique identifier.
        user_id (uuid.UUID): Identifier of owning user.
        fsrs_state (FsrsCardState): Memory state in database.
        fsrs_stability (float | None): Memory stability factor S.
        fsrs_difficulty (float | None): Memory difficulty factor D.
        fsrs_scheduled_days (int): Interval in days to next review.
        fsrs_learning_steps (int): Step count in initial learning phase.
        review_count (int): Total review repetitions count.
        lapse_count (int): Total lapses count.
        next_review_at (datetime | None): Scheduled review timestamp.
        last_reviewed_at (datetime | None): Previous review timestamp.
        saved_word_display (str): Display word text captured at save time.
        saved_lemma (str): Normalized dictionary lemma.
        saved_part_of_speech (str): Part of speech.
        saved_cefr_level (CefrLevel): CEFR complexity grade.
        saved_meaning_vi (str): Vietnamese contextual translation.
        saved_examples (list[dict[str, Any]]): Sentence examples snapshot.
        article_sentence_term_id (uuid.UUID): Source term identifier.
        sentence_id (uuid.UUID | None): Parent sentence identifier.
    """

    id: uuid.UUID
    user_id: uuid.UUID
    fsrs_state: FsrsCardState
    fsrs_stability: float | None
    fsrs_difficulty: float | None
    fsrs_scheduled_days: int
    fsrs_learning_steps: int
    review_count: int
    lapse_count: int
    next_review_at: datetime | None
    last_reviewed_at: datetime | None
    saved_word_display: str
    saved_lemma: str
    saved_part_of_speech: str
    saved_cefr_level: CefrLevel
    saved_meaning_vi: str
    saved_examples: list[dict[str, Any]]
    article_sentence_term_id: uuid.UUID
    sentence_id: uuid.UUID | None = None


class TutorCandidateService:
    """Provides bounded, prioritized vocabulary candidate pools for daily tutor sessions."""

    @classmethod
    def _map_vocab_to_candidate(cls, vocab: UserVocabulary) -> CandidateVocab:
        sentence_id = vocab.article_sentence_term.sentence_id if vocab.article_sentence_term else None
        return CandidateVocab(
            id=vocab.id,
            user_id=vocab.user_id,
            fsrs_state=vocab.fsrs_state,
            fsrs_stability=vocab.fsrs_stability,
            fsrs_difficulty=vocab.fsrs_difficulty,
            fsrs_scheduled_days=vocab.fsrs_scheduled_days,
            fsrs_learning_steps=vocab.fsrs_learning_steps,
            review_count=vocab.review_count,
            lapse_count=vocab.lapse_count,
            next_review_at=vocab.next_review_at,
            last_reviewed_at=vocab.last_reviewed_at,
            saved_word_display=vocab.saved_word_display,
            saved_lemma=vocab.saved_lemma,
            saved_part_of_speech=vocab.saved_part_of_speech,
            saved_cefr_level=vocab.saved_cefr_level,
            saved_meaning_vi=vocab.saved_meaning_vi,
            saved_examples=vocab.saved_examples or [],
            article_sentence_term_id=vocab.article_sentence_term_id,
            sentence_id=sentence_id,
        )

    @classmethod
    async def get_candidate_pool(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        now: datetime | None = None,
        limit: int = CANDIDATE_POOL_LIMIT,
    ) -> list[CandidateVocab]:
        """Fetches a deterministically-ordered candidate pool for the given user.

        Priority order:
        1. RELEARNING with next_review_at <= now
        2. LEARNING with next_review_at <= now
        3. REVIEW due or overdue (next_review_at <= now, oldest first)
        4. NEW words (oldest saved_at first)

        Args:
            db (AsyncSession): Active database session.
            user_id (uuid.UUID): Target user identifier.
            now (datetime | None, optional): Evaluation timestamp. Defaults to UTC now.
            limit (int, optional): Maximum candidates to return. Defaults to 50.

        Returns:
            list[CandidateVocab]: Prioritized candidate vocabulary entities.

        Example:
            >>> # candidates = await TutorCandidateService.get_candidate_pool(db, user_id)
        """
        eval_now = now or datetime.now(UTC)
        if eval_now.tzinfo is None:
            eval_now = eval_now.replace(tzinfo=UTC)

        bounded_limit = min(limit, CANDIDATE_POOL_LIMIT)

        # 1. Bucket 1: RELEARNING due
        q_relearning = (
            select(UserVocabulary)
            .options(selectinload(UserVocabulary.article_sentence_term))
            .where(
                UserVocabulary.user_id == user_id,
                UserVocabulary.fsrs_state == FsrsCardState.RELEARNING,
                UserVocabulary.next_review_at <= eval_now,
            )
            .order_by(
                UserVocabulary.next_review_at.asc(),
                UserVocabulary.saved_at.asc(),
                UserVocabulary.id.asc(),
            )
            .limit(bounded_limit)
        )
        res_relearning = await db.execute(q_relearning)
        relearning = res_relearning.scalars().all()

        # 2. Bucket 2: LEARNING due
        q_learning = (
            select(UserVocabulary)
            .options(selectinload(UserVocabulary.article_sentence_term))
            .where(
                UserVocabulary.user_id == user_id,
                UserVocabulary.fsrs_state == FsrsCardState.LEARNING,
                UserVocabulary.next_review_at <= eval_now,
            )
            .order_by(
                UserVocabulary.next_review_at.asc(),
                UserVocabulary.saved_at.asc(),
                UserVocabulary.id.asc(),
            )
            .limit(bounded_limit)
        )
        res_learning = await db.execute(q_learning)
        learning = res_learning.scalars().all()

        # 3. Bucket 3: REVIEW due or overdue
        q_review = (
            select(UserVocabulary)
            .options(selectinload(UserVocabulary.article_sentence_term))
            .where(
                UserVocabulary.user_id == user_id,
                UserVocabulary.fsrs_state == FsrsCardState.REVIEW,
                UserVocabulary.next_review_at <= eval_now,
            )
            .order_by(
                UserVocabulary.next_review_at.asc(),
                UserVocabulary.saved_at.asc(),
                UserVocabulary.id.asc(),
            )
            .limit(bounded_limit)
        )
        res_review = await db.execute(q_review)
        review = res_review.scalars().all()

        # 4. Bucket 4: NEW words (oldest saved_at first)
        q_new = (
            select(UserVocabulary)
            .options(selectinload(UserVocabulary.article_sentence_term))
            .where(
                UserVocabulary.user_id == user_id,
                UserVocabulary.fsrs_state == FsrsCardState.NEW,
            )
            .order_by(
                UserVocabulary.saved_at.asc(),
                UserVocabulary.id.asc(),
            )
            .limit(bounded_limit)
        )
        res_new = await db.execute(q_new)
        new_words = res_new.scalars().all()

        all_candidates = list(relearning) + list(learning) + list(review) + list(new_words)

        # 5. Fallback: if no candidates are due or new, fetch least-recently reviewed vocabulary
        if not all_candidates:
            q_fallback = (
                select(UserVocabulary)
                .options(selectinload(UserVocabulary.article_sentence_term))
                .where(UserVocabulary.user_id == user_id)
                .order_by(
                    UserVocabulary.last_reviewed_at.asc().nullsfirst(),
                    UserVocabulary.saved_at.asc(),
                    UserVocabulary.id.asc(),
                )
                .limit(bounded_limit)
            )
            res_fallback = await db.execute(q_fallback)
            fallback = res_fallback.scalars().all()
            return [cls._map_vocab_to_candidate(v) for v in fallback]

        return [cls._map_vocab_to_candidate(v) for v in all_candidates[:bounded_limit]]

    @classmethod
    async def count_new_vocab(cls, db: AsyncSession, user_id: uuid.UUID) -> int:
        """Returns the total number of unreviewed NEW vocabulary items for the user.

        Args:
            db (AsyncSession): Active database session.
            user_id (uuid.UUID): Target user identifier.

        Returns:
            int: Number of items with FSRS state NEW.

        Example:
            >>> # count = await TutorCandidateService.count_new_vocab(db, user_id)
        """
        stmt = (
            select(func.count())
            .select_from(UserVocabulary)
            .where(
                UserVocabulary.user_id == user_id,
                UserVocabulary.fsrs_state == FsrsCardState.NEW,
            )
        )
        result = await db.execute(stmt)
        return result.scalar() or 0
