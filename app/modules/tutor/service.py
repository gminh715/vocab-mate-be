"""Tutor service orchestrating daily sessions, AI activity generation, deterministic grading, and FSRS persistence."""

import base64
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import (
    FsrsCardState,
    TutorQuestionType,
    TutorSessionItemStatus,
    TutorSessionStatus,
)
from app.models.tutor import TutorSession, TutorSessionItem
from app.models.users import User
from app.models.vocabularies import UserVocabulary
from app.modules.ai.contracts import (
    SessionWarmupCandidate,
    SessionWarmupInput,
    TutorQuestionCandidate,
    TutorQuestionInput,
)
from app.modules.ai.service import AiService
from app.modules.tutor.candidate_service import (
    TutorCandidateService,
)
from app.modules.tutor.fsrs_service import (
    FsrsCardFields,
    TutorFsrsService,
)
from app.modules.tutor.rating_service import (
    RatingParams,
    TutorRatingService,
)
from app.modules.tutor.schemas import (
    RatingDistributionDto,
    SubmitAnswerDto,
    SubmitAnswerResponseDataDto,
    TodayStatusDataDto,
    TutorHistoryDataDto,
    TutorHistoryQueryDto,
    TutorSessionAnsweredItemDto,
    TutorSessionDetailDataDto,
    TutorSessionPendingItemDto,
    TutorSessionSummaryDto,
    TutorSessionSummaryStatsDto,
    TutorSessionWithItemDataDto,
)


class TutorService:
    """Core business logic service managing daily tutor sessions and FSRS spaced repetition."""

    def __init__(self) -> None:
        """Initializes dependencies for the Tutor service.

        Example:
            >>> service = TutorService()
        """
        self.fsrs_service = TutorFsrsService()
        self.ai_service = AiService()

    # ---------------------------------------------------------------------------
    # Response Mappers
    # ---------------------------------------------------------------------------

    @staticmethod
    def map_session_summary(session: TutorSession) -> TutorSessionSummaryDto:
        """Transforms a TutorSession ORM entity into a public summary DTO.

        Args:
            session (TutorSession): Database session entity.

        Returns:
            TutorSessionSummaryDto: Formatted summary DTO.

        Example:
            >>> # summary = TutorService.map_session_summary(session)
        """
        study_date_str = (
            session.study_date.strftime("%Y-%m-%d")
            if isinstance(session.study_date, datetime | type(datetime.now(UTC).date()))
            else str(session.study_date)[:10]
        )
        return TutorSessionSummaryDto(
            id=session.id,
            userId=session.user_id,
            studyDate=study_date_str,
            status=session.status,
            targetDurationMinutes=session.target_duration_minutes,
            targetActivityCount=session.target_activity_count,
            newWordTarget=session.new_word_target,
            warmupFacts=session.warmup_facts,
            startedAt=session.started_at,
            completedAt=session.completed_at,
            createdAt=session.created_at,
            updatedAt=session.updated_at,
        )

    @staticmethod
    def map_pending_item(item: TutorSessionItem) -> TutorSessionPendingItemDto:
        """Transforms a PENDING item, completely stripping private server-side grading specs.

        Args:
            item (TutorSessionItem): Database item entity.

        Returns:
            TutorSessionPendingItemDto: Safe public activity payload.

        Example:
            >>> # pending = TutorService.map_pending_item(item)
        """
        return TutorSessionPendingItemDto(
            id=item.id,
            sessionId=item.session_id,
            userVocabularyId=item.user_vocabulary_id,
            position=item.position,
            status=item.status,
            questionType=item.question_type,
            isNewWord=item.is_new_word,
            questionPayload=item.question_payload or {},
            hintUsed=item.hint_used,
            generatedAt=item.generated_at,
        )

    @classmethod
    def map_answered_item(cls, item: TutorSessionItem) -> TutorSessionAnsweredItemDto:
        """Transforms an ANSWERED item, revealing grading feedback and canonical answer keys.

        Args:
            item (TutorSessionItem): Database item entity.

        Returns:
            TutorSessionAnsweredItemDto: Comprehensive item review DTO.

        Example:
            >>> # answered = TutorService.map_answered_item(item)
        """
        base = cls.map_pending_item(item)
        grading = item.grading_spec or {}

        user_answer_val = item.user_answer
        if isinstance(user_answer_val, dict) and "value" in user_answer_val:
            user_answer_val = user_answer_val["value"]

        return TutorSessionAnsweredItemDto(
            id=base.id,
            sessionId=base.sessionId,
            userVocabularyId=base.userVocabularyId,
            position=base.position,
            status=base.status,
            questionType=base.questionType,
            isNewWord=base.isNewWord,
            questionPayload=base.questionPayload,
            hintUsed=base.hintUsed,
            generatedAt=base.generatedAt,
            userAnswer=user_answer_val,
            isCorrect=item.is_correct,
            responseTimeMs=item.response_time_ms,
            fsrsRating=item.fsrs_rating,
            feedbackVi=item.feedback_vi,
            correctAnswer=grading.get("correctAnswer"),
            explanationVi=grading.get("explanationVi"),
            answeredAt=item.answered_at,
        )

    @classmethod
    def calculate_summary_stats(
        cls,
        session: TutorSession,
        items: list[TutorSessionItem],
        next_due_count: int,
    ) -> TutorSessionSummaryStatsDto:
        """Computes deterministic performance and pacing statistics for a finished session.

        Args:
            session (TutorSession): Finished tutor session entity.
            items (list[TutorSessionItem]): All items belonging to session.
            next_due_count (int): Count of vocabulary items remaining due.

        Returns:
            TutorSessionSummaryStatsDto: Aggregated session performance metrics.

        Example:
            >>> # stats = TutorService.calculate_summary_stats(session, items, 0)
        """
        answered_items = [i for i in items if i.status == TutorSessionItemStatus.ANSWERED]

        if session.completed_at and session.started_at:
            duration_seconds = max(0, int((session.completed_at - session.started_at).total_seconds()))
        else:
            total_response_ms = sum(i.response_time_ms or 0 for i in answered_items)
            duration_seconds = total_response_ms // 1000

        correct_count = sum(1 for i in answered_items if i.is_correct is True)
        incorrect_count = sum(1 for i in answered_items if i.is_correct is False)
        new_words_studied = sum(1 for i in answered_items if i.is_new_word)
        review_words_studied = sum(1 for i in answered_items if not i.is_new_word)

        rating_distribution = RatingDistributionDto(
            again=sum(1 for i in answered_items if i.fsrs_rating == 1),
            hard=sum(1 for i in answered_items if i.fsrs_rating == 2),
            good=sum(1 for i in answered_items if i.fsrs_rating == 3),
            easy=sum(1 for i in answered_items if i.fsrs_rating == 4),
        )

        relearning_words_set: set[str] = set()
        for item in answered_items:
            if item.is_correct is False or item.fsrs_rating == 1:
                word_display = (item.question_payload or {}).get("wordDisplay")
                if word_display:
                    relearning_words_set.add(word_display)

        return TutorSessionSummaryStatsDto(
            durationSeconds=duration_seconds,
            plannedActivities=session.target_activity_count,
            completedActivities=len(answered_items),
            correctCount=correct_count,
            incorrectCount=incorrect_count,
            newWordsStudied=new_words_studied,
            reviewWordsStudied=review_words_studied,
            ratingDistribution=rating_distribution,
            relearningWords=sorted(relearning_words_set),
            nextDueCount=next_due_count,
        )

    # ---------------------------------------------------------------------------
    # Core Operations
    # ---------------------------------------------------------------------------

    @classmethod
    async def count_due_vocab(cls, db: AsyncSession, user_id: uuid.UUID, now: datetime) -> int:
        """Counts active flashcards due or overdue for review for the user.

        Args:
            db (AsyncSession): Active database session.
            user_id (uuid.UUID): Target user identifier.
            now (datetime): Evaluation timestamp.

        Returns:
            int: Number of due vocabulary items.

        Example:
            >>> # count = await TutorService.count_due_vocab(db, user_id, now)
        """
        stmt = (
            select(func.count())
            .select_from(UserVocabulary)
            .where(
                UserVocabulary.user_id == user_id,
                UserVocabulary.fsrs_state.in_(
                    [
                        FsrsCardState.RELEARNING,
                        FsrsCardState.LEARNING,
                        FsrsCardState.REVIEW,
                    ]
                ),
                UserVocabulary.next_review_at <= now,
            )
        )
        res = await db.execute(stmt)
        return res.scalar() or 0

    async def get_today_status(self, db: AsyncSession, user_id: uuid.UUID) -> TodayStatusDataDto:
        """Retrieves session readiness and status for today in Asia/Ho_Chi_Minh timezone.

        Args:
            db (AsyncSession): Active database session.
            user_id (uuid.UUID): Authenticated user identifier.

        Returns:
            TodayStatusDataDto: Eligibility flags and active session summary.

        Example:
            >>> # status = await tutor_service.get_today_status(db, user_id)
        """
        now = datetime.now(UTC)
        study_date_str = self.fsrs_service.get_study_date(now)
        study_date = datetime.strptime(study_date_str, "%Y-%m-%d").date()

        # Query session for today
        q_session = (
            select(TutorSession)
            .options(selectinload(TutorSession.items))
            .where(
                TutorSession.user_id == user_id,
                TutorSession.study_date == study_date,
            )
        )
        res_session = await db.execute(q_session)
        today_session = res_session.scalar_one_or_none()

        due_count = await self.count_due_vocab(db, user_id, now)

        q_total = select(func.count()).select_from(UserVocabulary).where(UserVocabulary.user_id == user_id)
        res_total = await db.execute(q_total)
        total_vocab_count = res_total.scalar() or 0

        if not today_session:
            return TodayStatusDataDto(
                canStart=(total_vocab_count > 0),
                canResume=False,
                isCompletedToday=False,
                isAbandoned=False,
                dueCount=due_count,
                session=None,
            )

        summary = self.map_session_summary(today_session)

        match today_session.status:
            case TutorSessionStatus.ACTIVE:
                return TodayStatusDataDto(
                    canStart=False,
                    canResume=True,
                    isCompletedToday=False,
                    isAbandoned=False,
                    dueCount=due_count,
                    session=summary,
                )
            case TutorSessionStatus.COMPLETED:
                return TodayStatusDataDto(
                    canStart=False,
                    canResume=False,
                    isCompletedToday=True,
                    isAbandoned=False,
                    dueCount=due_count,
                    session=summary,
                )
            case TutorSessionStatus.ABANDONED:
                return TodayStatusDataDto(
                    canStart=False,
                    canResume=False,
                    isCompletedToday=False,
                    isAbandoned=True,
                    dueCount=due_count,
                    session=summary,
                )

    async def start_or_resume_session(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> TutorSessionWithItemDataDto:
        """Starts a new daily tutor session or resumes an existing active one.

        Args:
            db (AsyncSession): Active database session.
            user_id (uuid.UUID): Authenticated user identifier.

        Returns:
            TutorSessionWithItemDataDto: Session summary and current pending activity item.

        Raises:
            HTTPException: If user has no saved vocabulary or user is not found.

        Example:
            >>> # session_data = await tutor_service.start_or_resume_session(db, user_id)
        """
        now = datetime.now(UTC)
        study_date_str = self.fsrs_service.get_study_date(now)
        study_date = datetime.strptime(study_date_str, "%Y-%m-%d").date()

        # 1. Check existing session for today
        q_session = (
            select(TutorSession)
            .options(selectinload(TutorSession.items))
            .where(
                TutorSession.user_id == user_id,
                TutorSession.study_date == study_date,
            )
        )
        res_session = await db.execute(q_session)
        session = res_session.scalar_one_or_none()

        if session:
            session_summary = self.map_session_summary(session)

            # 1a. Finished sessions
            if session.status in (TutorSessionStatus.COMPLETED, TutorSessionStatus.ABANDONED):
                due_count = await self.count_due_vocab(db, user_id, now)
                summary_stats = self.calculate_summary_stats(session, session.items, due_count)
                return TutorSessionWithItemDataDto(
                    session=session_summary,
                    currentItem=None,
                    summary=summary_stats,
                )

            # 1b. Check if active session already has a pending item
            pending_item = next(
                (i for i in session.items if i.status == TutorSessionItemStatus.PENDING),
                None,
            )
            if pending_item:
                return TutorSessionWithItemDataDto(
                    session=session_summary,
                    currentItem=self.map_pending_item(pending_item),
                    summary=None,
                )

            # 1c. Check if quota reached
            answered_count = sum(1 for i in session.items if i.status == TutorSessionItemStatus.ANSWERED)
            if answered_count >= session.target_activity_count:
                session.status = TutorSessionStatus.COMPLETED
                session.completed_at = now
                session.updated_at = now
                items_snapshot = list(session.items)
                await db.commit()
                await db.refresh(session)
                due_count = await self.count_due_vocab(db, user_id, now)
                summary_stats = self.calculate_summary_stats(session, items_snapshot, due_count)
                return TutorSessionWithItemDataDto(
                    session=self.map_session_summary(session),
                    currentItem=None,
                    summary=summary_stats,
                )

            # 1d. Generate next activity item
            new_item = await self._generate_and_persist_next_item(db, session, session.items)
            await db.commit()
            return TutorSessionWithItemDataDto(
                session=session_summary,
                currentItem=new_item,
                summary=None,
            )

        # 2. No session today: check prerequisites
        q_user = select(User).where(User.id == user_id)
        res_user = await db.execute(q_user)
        user = res_user.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        q_total = select(func.count()).select_from(UserVocabulary).where(UserVocabulary.user_id == user_id)
        total_vocab = (await db.execute(q_total)).scalar() or 0
        if total_vocab == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No saved vocabulary found. Please save words from articles before starting a tutor session.",
            )

        new_vocab_count = await TutorCandidateService.count_new_vocab(db, user_id)
        daily_minutes = user.daily_study_minutes or 10
        targets = self.fsrs_service.calc_session_targets(daily_minutes, new_vocab_count)

        # 3. Optional warmup stories for relearning candidates
        warmup_facts: list[dict[str, Any]] | None = None
        try:
            pool = await TutorCandidateService.get_candidate_pool(db, user_id, now)
            relearning_candidates = [c for c in pool if c.fsrs_state == FsrsCardState.RELEARNING]
            if relearning_candidates:
                warmup_input = SessionWarmupInput(
                    candidates=[
                        SessionWarmupCandidate(
                            word_display=c.saved_word_display,
                            lemma=c.saved_lemma,
                            part_of_speech=c.saved_part_of_speech,
                            meaning_vi=c.saved_meaning_vi,
                        )
                        for c in relearning_candidates[:5]
                    ]
                )
                warmup_result = await self.ai_service.generate_session_warmup_facts(warmup_input)
                if warmup_result.facts:
                    warmup_facts = [f.model_dump() for f in warmup_result.facts]
        except Exception:
            warmup_facts = None

        # 4. Create new TutorSession
        new_session = TutorSession(
            id=uuid.uuid4(),
            user_id=user_id,
            study_date=study_date,
            status=TutorSessionStatus.ACTIVE,
            target_duration_minutes=daily_minutes,
            target_activity_count=targets.target_activity_count,
            new_word_target=targets.new_word_target,
            warmup_facts=warmup_facts,
            started_at=now,
        )
        db.add(new_session)
        await db.flush()

        # 5. Generate first activity item
        first_item = await self._generate_and_persist_next_item(db, new_session, [])
        await db.commit()

        return TutorSessionWithItemDataDto(
            session=self.map_session_summary(new_session),
            currentItem=first_item,
            summary=None,
        )

    async def get_session(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> TutorSessionWithItemDataDto:
        """Retrieves session state, active question, or completion summary by ID.

        Args:
            db (AsyncSession): Active database session.
            user_id (uuid.UUID): Authenticated user identifier.
            session_id (uuid.UUID): Target session identifier.

        Returns:
            TutorSessionWithItemDataDto: Session state representation.

        Raises:
            HTTPException: 404 if session not found.

        Example:
            >>> # session = await tutor_service.get_session(db, user_id, session_id)
        """
        now = datetime.now(UTC)
        stmt = (
            select(TutorSession)
            .options(selectinload(TutorSession.items))
            .where(TutorSession.id == session_id, TutorSession.user_id == user_id)
        )
        res = await db.execute(stmt)
        session = res.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tutor session not found")

        session_summary = self.map_session_summary(session)

        if session.status in (TutorSessionStatus.COMPLETED, TutorSessionStatus.ABANDONED):
            due_count = await self.count_due_vocab(db, user_id, now)
            summary_stats = self.calculate_summary_stats(session, session.items, due_count)
            return TutorSessionWithItemDataDto(
                session=session_summary,
                currentItem=None,
                summary=summary_stats,
            )

        pending_item = next(
            (i for i in session.items if i.status == TutorSessionItemStatus.PENDING),
            None,
        )
        if pending_item:
            return TutorSessionWithItemDataDto(
                session=session_summary,
                currentItem=self.map_pending_item(pending_item),
                summary=None,
            )

        answered_count = sum(1 for i in session.items if i.status == TutorSessionItemStatus.ANSWERED)
        if answered_count >= session.target_activity_count:
            session.status = TutorSessionStatus.COMPLETED
            session.completed_at = now
            session.updated_at = now
            items_snapshot = list(session.items)
            await db.commit()
            await db.refresh(session)
            due_count = await self.count_due_vocab(db, user_id, now)
            summary_stats = self.calculate_summary_stats(session, items_snapshot, due_count)
            return TutorSessionWithItemDataDto(
                session=self.map_session_summary(session),
                currentItem=None,
                summary=summary_stats,
            )

        new_item = await self._generate_and_persist_next_item(db, session, session.items)
        await db.commit()
        return TutorSessionWithItemDataDto(
            session=session_summary,
            currentItem=new_item,
            summary=None,
        )

    async def get_session_detail(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> TutorSessionDetailDataDto:
        """Retrieves full session history review revealing all canonical answers and explanations.

        Args:
            db (AsyncSession): Active database session.
            user_id (uuid.UUID): Authenticated user identifier.
            session_id (uuid.UUID): Target session identifier.

        Returns:
            TutorSessionDetailDataDto: Full question history and summary.

        Raises:
            HTTPException: 404 if session not found.

        Example:
            >>> # detail = await tutor_service.get_session_detail(db, user_id, session_id)
        """
        stmt = (
            select(TutorSession)
            .options(selectinload(TutorSession.items))
            .where(TutorSession.id == session_id, TutorSession.user_id == user_id)
        )
        res = await db.execute(stmt)
        session = res.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tutor session not found")

        session_summary = self.map_session_summary(session)
        sorted_items = sorted(session.items, key=lambda x: x.position)
        mapped_items = [self.map_answered_item(i) for i in sorted_items]

        now = datetime.now(UTC)
        due_count = await self.count_due_vocab(db, user_id, now)
        summary_stats = self.calculate_summary_stats(session, session.items, due_count)

        return TutorSessionDetailDataDto(
            session=session_summary,
            items=mapped_items,
            summary=summary_stats,
        )

    async def submit_answer(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        item_id: uuid.UUID,
        dto: SubmitAnswerDto,
    ) -> SubmitAnswerResponseDataDto:
        """Evaluates learner answer deterministically and updates FSRS parameters atomically.

        Args:
            db (AsyncSession): Active database session.
            user_id (uuid.UUID): Authenticated user identifier.
            session_id (uuid.UUID): Target session identifier.
            item_id (uuid.UUID): Target activity item identifier.
            dto (SubmitAnswerDto): Answer payload.

        Returns:
            SubmitAnswerResponseDataDto: Grading feedback and updated session status.

        Raises:
            HTTPException: 404 if session or item not found.
            HTTPException: 400 if item is already answered or session is not active.

        Example:
            >>> # result = await tutor_service.submit_answer(db, user_id, session_id, item_id, dto)
        """
        now = datetime.now(UTC)

        stmt = (
            select(TutorSession)
            .options(selectinload(TutorSession.items))
            .where(TutorSession.id == session_id, TutorSession.user_id == user_id)
        )
        res = await db.execute(stmt)
        session = res.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tutor session not found")

        if session.status != TutorSessionStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only active sessions accept answers")

        item = next((i for i in session.items if i.id == item_id), None)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity item not found")

        if item.status != TutorSessionItemStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Activity item has already been answered"
            )

        grading = item.grading_spec or {}
        correct_answer = grading.get("correctAnswer")

        # 1. Deterministic grading
        is_correct = self._grade_answer(item.question_type, dto.answer, correct_answer)

        # 2. FSRS rating calculation
        fsrs_rating_val = 1 if not is_correct else 3
        if item.user_vocabulary_id:
            q_vocab = select(UserVocabulary).where(UserVocabulary.id == item.user_vocabulary_id)
            res_vocab = await db.execute(q_vocab)
            vocab = res_vocab.scalar_one_or_none()
            if vocab:
                rating_params = RatingParams(
                    is_correct=is_correct,
                    hint_used=dto.hintUsed,
                    response_time_ms=dto.responseTimeMs,
                    question_type=item.question_type,
                    fsrs_state=vocab.fsrs_state,
                    review_count=vocab.review_count,
                )
                fsrs_rating = TutorRatingService.map_to_fsrs_rating(rating_params)
                fsrs_rating_val = fsrs_rating.value

                card_fields = FsrsCardFields(
                    fsrs_state=vocab.fsrs_state,
                    fsrs_stability=vocab.fsrs_stability,
                    fsrs_difficulty=vocab.fsrs_difficulty,
                    fsrs_scheduled_days=vocab.fsrs_scheduled_days,
                    fsrs_learning_steps=vocab.fsrs_learning_steps,
                    review_count=vocab.review_count,
                    lapse_count=vocab.lapse_count,
                    next_review_at=vocab.next_review_at,
                    last_reviewed_at=vocab.last_reviewed_at,
                )
                fsrs_card = self.fsrs_service.build_fsrs_card(card_fields)
                sched_res = self.fsrs_service.schedule_fsrs_card(fsrs_card, fsrs_rating, now)
                vocab_update = self.fsrs_service.map_card_to_update(
                    sched_res, now, vocab.review_count, vocab.lapse_count
                )

                # Update UserVocabulary
                vocab.fsrs_state = vocab_update.fsrs_state
                vocab.fsrs_stability = vocab_update.fsrs_stability
                vocab.fsrs_difficulty = vocab_update.fsrs_difficulty
                vocab.fsrs_scheduled_days = vocab_update.fsrs_scheduled_days
                vocab.fsrs_learning_steps = vocab_update.fsrs_learning_steps
                vocab.review_count = vocab_update.review_count
                vocab.lapse_count = vocab_update.lapse_count
                vocab.next_review_at = vocab_update.next_review_at
                vocab.last_reviewed_at = vocab_update.last_reviewed_at

        feedback_vi = (
            grading.get("feedbackCorrectVi", "Chính xác!")
            if is_correct
            else grading.get("feedbackIncorrectVi", "Chưa chính xác.")
        )

        item.status = TutorSessionItemStatus.ANSWERED
        item.user_answer = {"value": dto.answer} if not isinstance(dto.answer, dict) else dto.answer
        item.is_correct = is_correct
        item.hint_used = dto.hintUsed
        item.response_time_ms = dto.responseTimeMs
        item.fsrs_rating = fsrs_rating_val
        item.feedback_vi = feedback_vi
        item.answered_at = now

        answered_count = sum(1 for i in session.items if i.status == TutorSessionItemStatus.ANSWERED)
        is_completed = answered_count >= session.target_activity_count
        if is_completed:
            session.status = TutorSessionStatus.COMPLETED
            session.completed_at = now
            session.updated_at = now

        await db.commit()
        await db.refresh(item)
        await db.refresh(session)

        return SubmitAnswerResponseDataDto(
            item=self.map_answered_item(item),
            sessionStatus=session.status,
            isSessionCompleted=is_completed,
        )

    async def abandon_session(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> TutorSessionWithItemDataDto:
        """Abandons an active tutor session and marks all pending items as skipped.

        Args:
            db (AsyncSession): Active database session.
            user_id (uuid.UUID): Authenticated user identifier.
            session_id (uuid.UUID): Target session identifier.

        Returns:
            TutorSessionWithItemDataDto: Session summary and performance statistics.

        Raises:
            HTTPException: 404 if session not found, 400 if session is not active.

        Example:
            >>> # abandoned = await tutor_service.abandon_session(db, user_id, session_id)
        """
        now = datetime.now(UTC)
        stmt = (
            select(TutorSession)
            .options(selectinload(TutorSession.items))
            .where(TutorSession.id == session_id, TutorSession.user_id == user_id)
        )
        res = await db.execute(stmt)
        session = res.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tutor session not found")

        if session.status != TutorSessionStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only active sessions can be abandoned")

        session.status = TutorSessionStatus.ABANDONED
        session.completed_at = now
        session.updated_at = now

        for item in session.items:
            if item.status == TutorSessionItemStatus.PENDING:
                item.status = TutorSessionItemStatus.SKIPPED

        items_snapshot = list(session.items)

        await db.commit()
        await db.refresh(session)

        due_count = await self.count_due_vocab(db, user_id, now)
        summary_stats = self.calculate_summary_stats(session, items_snapshot, due_count)

        return TutorSessionWithItemDataDto(
            session=self.map_session_summary(session),
            currentItem=None,
            summary=summary_stats,
        )

    async def get_history(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        query: TutorHistoryQueryDto,
    ) -> TutorHistoryDataDto:
        """Retrieves paginated historical sessions using cursor-based keyset pagination.

        Args:
            db (AsyncSession): Active database session.
            user_id (uuid.UUID): Authenticated user identifier.
            query (TutorHistoryQueryDto): Keyset cursor and limit.

        Returns:
            TutorHistoryDataDto: Paginated historical session summaries and next cursor.

        Example:
            >>> # history = await tutor_service.get_history(db, user_id, query)
        """
        limit = query.limit
        stmt = select(TutorSession).where(TutorSession.user_id == user_id)

        if query.cursor:
            try:
                decoded = json.loads(base64.b64decode(query.cursor.encode("utf-8")).decode("utf-8"))
                cursor_date = datetime.strptime(decoded["studyDate"], "%Y-%m-%d").date()
                cursor_id = uuid.UUID(decoded["id"])

                stmt = stmt.where(
                    (TutorSession.study_date < cursor_date)
                    | ((TutorSession.study_date == cursor_date) & (TutorSession.id < cursor_id))
                )
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid pagination cursor",
                ) from None

        stmt = stmt.order_by(TutorSession.study_date.desc(), TutorSession.id.desc()).limit(limit + 1)
        res = await db.execute(stmt)
        sessions = res.scalars().all()

        has_more = len(sessions) > limit
        page_sessions = sessions[:limit] if has_more else sessions

        next_cursor = None
        if has_more and page_sessions:
            last_sess = page_sessions[-1]
            last_date_str = (
                last_sess.study_date.strftime("%Y-%m-%d")
                if isinstance(last_sess.study_date, datetime | type(datetime.now(UTC).date()))
                else str(last_sess.study_date)[:10]
            )
            cursor_payload = {"studyDate": last_date_str, "id": str(last_sess.id)}
            next_cursor = base64.b64encode(json.dumps(cursor_payload).encode("utf-8")).decode("utf-8")

        return TutorHistoryDataDto(
            items=[self.map_session_summary(s) for s in page_sessions],
            nextCursor=next_cursor,
            hasMore=has_more,
        )

    # ---------------------------------------------------------------------------
    # Internal Question Generation & Grading
    # ---------------------------------------------------------------------------

    @staticmethod
    def _grade_answer(
        question_type: TutorQuestionType,
        user_answer: Any,
        correct_answer: Any,
    ) -> bool:
        """Evaluates user submission deterministically against canonical answer key."""
        if user_answer is None or correct_answer is None:
            return False

        user_str = str(user_answer).strip()
        correct_str = str(correct_answer).strip()
        if not user_str or not correct_str:
            return False

        if question_type == TutorQuestionType.MULTIPLE_CHOICE:
            return user_str.upper() == correct_str.upper()

        norm_user = TutorRatingService.normalize_typed_answer(user_str)
        norm_correct = TutorRatingService.normalize_typed_answer(correct_str)
        return norm_user == norm_correct

    @staticmethod
    def _map_fsrs_state_to_question_type(fsrs_state: FsrsCardState) -> TutorQuestionType:
        """Maps an FSRS memory state to its pedagogical question type."""
        match fsrs_state:
            case FsrsCardState.NEW:
                return TutorQuestionType.MULTIPLE_CHOICE
            case FsrsCardState.LEARNING:
                return TutorQuestionType.CONTEXTUAL_CLOZE
            case FsrsCardState.REVIEW:
                return TutorQuestionType.TYPED_RECALL
            case FsrsCardState.RELEARNING:
                return TutorQuestionType.MICRO_LESSON_RETEST
            case _:
                return TutorQuestionType.MULTIPLE_CHOICE

    async def _generate_and_persist_next_item(
        self,
        db: AsyncSession,
        session: TutorSession,
        existing_items: list[TutorSessionItem],
    ) -> TutorSessionPendingItemDto:
        """Selects priority candidate and invokes AI service to generate next activity item.

        Args:
            db (AsyncSession): Active database session.
            session (TutorSession): Parent tutor session instance.
            existing_items (list[TutorSessionItem]): List of already created activity items.

        Returns:
            TutorSessionPendingItemDto: Safe client representation of the pending question.

        Raises:
            HTTPException: If no candidate vocabulary items are available.
        """
        now = datetime.now(UTC)
        candidates = await TutorCandidateService.get_candidate_pool(db, session.user_id, now)
        if not candidates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No candidate vocabulary items available for this session",
            )

        # Quota selection
        new_words_so_far = sum(1 for i in existing_items if i.is_new_word)
        remaining_new_quota = max(0, session.new_word_target - new_words_so_far)
        remaining_total_activities = session.target_activity_count - len(existing_items)

        used_vocab_ids = {i.user_vocabulary_id for i in existing_items if i.user_vocabulary_id}
        unused_candidates = [c for c in candidates if c.id not in used_vocab_ids]
        pool = unused_candidates if unused_candidates else candidates

        if remaining_new_quota >= remaining_total_activities:
            selected = next((c for c in pool if c.fsrs_state == FsrsCardState.NEW), pool[0])
        else:
            selected = pool[0]

        question_type = self._map_fsrs_state_to_question_type(selected.fsrs_state)

        # AI generation outside transaction
        ai_candidate = TutorQuestionCandidate(
            id=str(selected.id),
            word_display=selected.saved_word_display,
            lemma=selected.saved_lemma,
            part_of_speech=selected.saved_part_of_speech,
            meaning_vi=selected.saved_meaning_vi,
            examples=selected.saved_examples,
        )
        ai_input = TutorQuestionInput(
            allowlist_ids=[str(selected.id)],
            candidates=[ai_candidate],
            question_type=question_type,
        )

        ai_result = await self.ai_service.generate_tutor_activity(ai_input)

        # Build public question payload and private grading spec
        base_payload = {
            "questionPromptVi": ai_result.question_prompt_vi,
            "wordDisplay": selected.saved_word_display,
            "meaningVi": selected.saved_meaning_vi,
        }

        match ai_result.question_type:
            case TutorQuestionType.MULTIPLE_CHOICE:
                question_payload = {
                    **base_payload,
                    "options": [opt.model_dump() for opt in ai_result.options],
                }
                grading_spec = {
                    "correctAnswer": ai_result.correct_option_id,
                    "explanationVi": ai_result.explanation_vi,
                    "feedbackCorrectVi": ai_result.feedback_correct_vi,
                    "feedbackIncorrectVi": ai_result.feedback_incorrect_vi,
                }
            case TutorQuestionType.CONTEXTUAL_CLOZE:
                question_payload = {
                    **base_payload,
                    "sentenceWithBlank": ai_result.sentence_with_blank,
                }
                grading_spec = {
                    "correctAnswer": ai_result.canonical_answer,
                    "explanationVi": ai_result.explanation_vi,
                    "feedbackCorrectVi": ai_result.feedback_correct_vi,
                    "feedbackIncorrectVi": ai_result.feedback_incorrect_vi,
                }
            case TutorQuestionType.TYPED_RECALL:
                question_payload = {
                    **base_payload,
                    "recallPromptVi": ai_result.recall_prompt_vi,
                }
                grading_spec = {
                    "correctAnswer": ai_result.canonical_answer,
                    "explanationVi": ai_result.explanation_vi,
                    "feedbackCorrectVi": ai_result.feedback_correct_vi,
                    "feedbackIncorrectVi": ai_result.feedback_incorrect_vi,
                }
            case TutorQuestionType.MICRO_LESSON_RETEST:
                question_payload = {
                    **base_payload,
                    "microLessonTitle": ai_result.micro_lesson_title,
                    "microLessonFactEn": ai_result.micro_lesson_fact_en,
                    "microLessonFactVi": ai_result.micro_lesson_fact_vi,
                    "microLessonVi": ai_result.micro_lesson_vi,
                    "retestType": ai_result.retest_type.value if ai_result.retest_type else None,
                    "sentenceWithBlank": ai_result.sentence_with_blank,
                    "recallPromptVi": ai_result.recall_prompt_vi,
                }
                grading_spec = {
                    "correctAnswer": ai_result.canonical_answer,
                    "explanationVi": ai_result.explanation_vi,
                    "feedbackCorrectVi": ai_result.feedback_correct_vi,
                    "feedbackIncorrectVi": ai_result.feedback_incorrect_vi,
                    "retestType": ai_result.retest_type.value if ai_result.retest_type else None,
                }

        next_position = len(existing_items) + 1
        persisted_item = TutorSessionItem(
            id=uuid.uuid4(),
            session_id=session.id,
            session=session,
            user_vocabulary_id=selected.id,
            position=next_position,
            status=TutorSessionItemStatus.PENDING,
            question_type=question_type,
            is_new_word=(selected.fsrs_state == FsrsCardState.NEW),
            question_payload=question_payload,
            grading_spec=grading_spec,
            hint_used=False,
            generated_at=now,
        )
        db.add(persisted_item)
        await db.commit()
        await db.refresh(persisted_item)

        return self.map_pending_item(persisted_item)
