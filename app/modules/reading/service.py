"""Service layer for the Reading module managing learner reader sessions, progress, and AI enrichment."""

import json
import math
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.articles import Article, ArticleSentence, ArticleSentenceTerm
from app.models.enums import AiGenerationStatus, ArticleStatus, CefrLevel, ReadingStatus, TermReviewStatus
from app.models.reading import UserArticleProgress
from app.models.users import User
from app.models.vocabularies import UserVocabulary
from app.modules.ai.contracts import TermEnrichmentInput
from app.modules.ai.service import AiService
from app.modules.articles.helpers.html_sanitizer import HtmlSanitizerHelper
from app.modules.categories.schemas import PublicCategoryDto
from app.modules.reading.schemas import (
    ContextualParentSentenceDto,
    ContextualTermDto,
    ContextualTermLookupDataDto,
    ContextualTermSaveStateDto,
    PaginationMetaDto,
    ReaderArticleDataDto,
    ReaderArticleDto,
    ReaderProgressDto,
    ReadingHistoryArticleDto,
    ReadingHistoryDataDto,
    ReadingHistoryItemDto,
    ReadingHistoryQueryDto,
    ReadingProgressDataDto,
    UpdateReadingProgressDto,
)


class ReadingService:
    """Service managing learner reading sessions, progress tracking, and contextual lookups.

    Example:
        >>> # ReadingService methods are class methods invoked with an active AsyncSession
    """

    @classmethod
    async def get_reader_article(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        slug: str,
    ) -> ReaderArticleDataDto:
        """Retrieves the personalized reader payload for a published article slug.

        Args:
            db (AsyncSession): Active database session.
            user_id (uuid.UUID): Target learner unique identifier.
            slug (str): Unique URL-friendly slug of the published article.

        Returns:
            ReaderArticleDataDto: Enriched article reader data with highlights and progress.

        Raises:
            HTTPException: 404 if user or published article is not found.

        Example:
            >>> # data = await ReadingService.get_reader_article(db, user_id, "tech-news")
        """
        user_res = await db.execute(select(User).where(User.id == user_id))
        user = user_res.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        art_stmt = (
            select(Article)
            .options(selectinload(Article.category))
            .where(Article.slug == slug, Article.status == ArticleStatus.PUBLISHED)
        )
        art_res = await db.execute(art_stmt)
        article = art_res.scalar_one_or_none()
        if not article:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Published article not found")

        # Query active candidate terms
        terms_stmt = (
            select(ArticleSentenceTerm)
            .join(ArticleSentence, ArticleSentenceTerm.sentence_id == ArticleSentence.id)
            .where(
                ArticleSentence.article_id == article.id,
                ArticleSentence.content_version == article.content_version,
                ArticleSentence.is_active.is_(True),
                ArticleSentenceTerm.is_active.is_(True),
                ArticleSentenceTerm.is_lookup_enabled.is_(True),
                ArticleSentenceTerm.review_status == TermReviewStatus.APPROVED,
            )
            .order_by(ArticleSentenceTerm.id.asc())
        )
        terms_res = await db.execute(terms_stmt)
        terms = terms_res.scalars().all()

        # Personalized highlight calculation
        cefr_rank = {
            CefrLevel.A1: 1,
            CefrLevel.A2: 2,
            CefrLevel.B1: 3,
            CefrLevel.B2: 4,
            CefrLevel.C1: 5,
            CefrLevel.C2: 6,
        }
        user_cefr = user.current_cefr_level
        target_cefr = user.learning_goal if user.learning_goal in CefrLevel.__members__ else None

        if user_cefr and target_cefr:
            highlighted_ids = [
                str(t.id)
                for t in terms
                if t.cefr_level
                and cefr_rank.get(user_cefr, 1) <= cefr_rank.get(t.cefr_level, 0) <= cefr_rank.get(target_cefr, 6)
            ]
        elif user_cefr:
            highlighted_ids = [
                str(t.id)
                for t in terms
                if t.cefr_level and cefr_rank.get(t.cefr_level, 0) >= cefr_rank.get(user_cefr, 1)
            ]
        else:
            highlighted_ids = [
                str(t.id)
                for t in terms
                if t.cefr_level and cefr_rank.get(t.cefr_level, 0) >= 3  # B1 and above by default
            ]

        # Reading progress
        prog_stmt = select(UserArticleProgress).where(
            UserArticleProgress.user_id == user_id,
            UserArticleProgress.article_id == article.id,
        )
        prog_res = await db.execute(prog_stmt)
        progress = prog_res.scalar_one_or_none()

        if progress:
            prog_dto = ReaderProgressDto(
                articleId=article.id,
                status=ReadingStatus.COMPLETED if progress.completed_at else ReadingStatus.READING,
                progressPercent=float(progress.progress_percent or 0.0),
                completedAt=progress.completed_at,
            )
        else:
            prog_dto = ReaderProgressDto(
                articleId=article.id,
                status=ReadingStatus.READING,
                progressPercent=0.0,
                completedAt=None,
            )

        sanitized_html = HtmlSanitizerHelper.sanitize(article.content_html)
        reader_article = ReaderArticleDto.model_validate(article)

        return ReaderArticleDataDto(
            article=reader_article,
            contentHtml=sanitized_html,
            highlightedTermIds=highlighted_ids,
            progress=prog_dto,
        )

    @classmethod
    async def get_history(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        query: ReadingHistoryQueryDto,
    ) -> ReadingHistoryDataDto:
        """Retrieves paginated reading progress history for the authenticated user.

        Args:
            db (AsyncSession): Active database session.
            user_id (uuid.UUID): Target learner unique identifier.
            query (ReadingHistoryQueryDto): Query parameters for pagination, status, and sorting.

        Returns:
            ReadingHistoryDataDto: Reading history items with pagination metadata.

        Example:
            >>> # history = await ReadingService.get_history(db, user_id, query)
        """
        stmt = (
            select(UserArticleProgress)
            .options(selectinload(UserArticleProgress.article).selectinload(Article.category))
            .where(UserArticleProgress.user_id == user_id)
        )
        if query.status == ReadingStatus.COMPLETED:
            stmt = stmt.where(UserArticleProgress.completed_at.is_not(None))
        elif query.status == ReadingStatus.READING:
            stmt = stmt.where(UserArticleProgress.completed_at.is_(None))

        count_stmt = select(func.count()).select_from(UserArticleProgress).where(UserArticleProgress.user_id == user_id)
        if query.status == ReadingStatus.COMPLETED:
            count_stmt = count_stmt.where(UserArticleProgress.completed_at.is_not(None))
        elif query.status == ReadingStatus.READING:
            count_stmt = count_stmt.where(UserArticleProgress.completed_at.is_(None))

        total = (await db.execute(count_stmt)).scalar_one()

        order_col = (
            UserArticleProgress.last_read_at.asc()
            if query.sort == "oldest"
            else UserArticleProgress.last_read_at.desc()
        )
        stmt = (
            stmt.order_by(order_col, UserArticleProgress.id.asc())
            .offset((query.page - 1) * query.limit)
            .limit(query.limit)
        )

        res = await db.execute(stmt)
        rows = res.scalars().all()

        items = []
        for r in rows:
            items.append(
                ReadingHistoryItemDto(
                    articleId=r.article_id,
                    status=ReadingStatus.COMPLETED if r.completed_at else ReadingStatus.READING,
                    progressPercent=float(r.progress_percent or 0.0),
                    completedAt=r.completed_at,
                    firstOpenedAt=r.first_opened_at,
                    lastReadAt=r.last_read_at,
                    article=ReadingHistoryArticleDto(
                        id=r.article.id,
                        title=r.article.title,
                        slug=r.article.slug,
                        summary=r.article.summary,
                        thumbnailUrl=r.article.thumbnail_url,
                        cefrLevel=r.article.cefr_level,
                        status=r.article.status,
                        publishedAt=r.article.published_at,
                        category=PublicCategoryDto.model_validate(r.article.category),
                    ),
                )
            )

        return ReadingHistoryDataDto(
            items=items,
            meta=PaginationMetaDto(
                page=query.page,
                limit=query.limit,
                total=total,
                totalPages=math.ceil(total / query.limit) if query.limit > 0 else 0,
            ),
        )

    @classmethod
    async def get_progress(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        article_id: uuid.UUID,
    ) -> ReadingProgressDataDto:
        """Retrieves reading progress for an article, falling back to a non-persisted default.

        Args:
            db (AsyncSession): Active database session.
            user_id (uuid.UUID): Target learner unique identifier.
            article_id (uuid.UUID): Target article unique identifier.

        Returns:
            ReadingProgressDataDto: Reading progress information.

        Raises:
            HTTPException: 404 if published article does not exist.

        Example:
            >>> # prog = await ReadingService.get_progress(db, user_id, article_id)
        """
        art = await db.scalar(
            select(Article).where(Article.id == article_id, Article.status == ArticleStatus.PUBLISHED)
        )
        if not art:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Published article not found")

        prog = await db.scalar(
            select(UserArticleProgress).where(
                UserArticleProgress.user_id == user_id,
                UserArticleProgress.article_id == article_id,
            )
        )
        if prog:
            prog_dto = ReaderProgressDto(
                articleId=article_id,
                status=ReadingStatus.COMPLETED if prog.completed_at else ReadingStatus.READING,
                progressPercent=float(prog.progress_percent or 0.0),
                completedAt=prog.completed_at,
            )
        else:
            prog_dto = ReaderProgressDto(
                articleId=article_id,
                status=ReadingStatus.READING,
                progressPercent=0.0,
                completedAt=None,
            )
        return ReadingProgressDataDto(progress=prog_dto)

    @classmethod
    async def update_progress(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        article_id: uuid.UUID,
        dto: UpdateReadingProgressDto,
    ) -> ReadingProgressDataDto:
        """Creates or partially updates owner-scoped reading progress.

        Args:
            db (AsyncSession): Active database session.
            user_id (uuid.UUID): Target learner unique identifier.
            article_id (uuid.UUID): Target article unique identifier.
            dto (UpdateReadingProgressDto): New progress values.

        Returns:
            ReadingProgressDataDto: Updated reading progress state.

        Raises:
            HTTPException: 404 if published article is not found.

        Example:
            >>> # prog = await ReadingService.update_progress(db, user_id, article_id, dto)
        """
        art = await db.scalar(
            select(Article).where(Article.id == article_id, Article.status == ArticleStatus.PUBLISHED)
        )
        if not art:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Published article not found")

        prog = await db.scalar(
            select(UserArticleProgress).where(
                UserArticleProgress.user_id == user_id,
                UserArticleProgress.article_id == article_id,
            )
        )
        now = datetime.now(UTC)
        if prog:
            is_completed = prog.completed_at is not None
            prog.last_read_at = now
            if is_completed:
                prog.progress_percent = Decimal(100)
            else:
                prog.progress_percent = dto.progressPercent
        else:
            prog = UserArticleProgress(
                id=uuid.uuid4(),
                user_id=user_id,
                article_id=article_id,
                progress_percent=dto.progressPercent,
                first_opened_at=now,
                last_read_at=now,
                completed_at=None,
            )
            db.add(prog)

        await db.commit()
        await db.refresh(prog)

        status_val = ReadingStatus.COMPLETED if prog.completed_at else ReadingStatus.READING
        return ReadingProgressDataDto(
            progress=ReaderProgressDto(
                articleId=article_id,
                status=status_val,
                progressPercent=float(prog.progress_percent or 0.0),
                completedAt=prog.completed_at,
            )
        )

    @classmethod
    async def complete_progress(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        article_id: uuid.UUID,
    ) -> ReadingProgressDataDto:
        """Marks owner-scoped reading progress as completed (100%).

        Args:
            db (AsyncSession): Active database session.
            user_id (uuid.UUID): Target learner unique identifier.
            article_id (uuid.UUID): Target article unique identifier.

        Returns:
            ReadingProgressDataDto: Completed reading progress state.

        Raises:
            HTTPException: 404 if published article is not found.

        Example:
            >>> # prog = await ReadingService.complete_progress(db, user_id, article_id)
        """
        art = await db.scalar(
            select(Article).where(Article.id == article_id, Article.status == ArticleStatus.PUBLISHED)
        )
        if not art:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Published article not found")

        prog = await db.scalar(
            select(UserArticleProgress).where(
                UserArticleProgress.user_id == user_id,
                UserArticleProgress.article_id == article_id,
            )
        )
        now = datetime.now(UTC)
        if prog:
            prog.last_read_at = now
            prog.progress_percent = Decimal(100)
            if not prog.completed_at:
                prog.completed_at = now
        else:
            prog = UserArticleProgress(
                id=uuid.uuid4(),
                user_id=user_id,
                article_id=article_id,
                progress_percent=Decimal(100),
                first_opened_at=now,
                last_read_at=now,
                completed_at=now,
            )
            db.add(prog)

        await db.commit()
        await db.refresh(prog)

        return ReadingProgressDataDto(
            progress=ReaderProgressDto(
                articleId=article_id,
                status=ReadingStatus.COMPLETED,
                progressPercent=100.0,
                completedAt=prog.completed_at,
            )
        )

    @classmethod
    async def delete_progress(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        article_id: uuid.UUID,
    ) -> None:
        """Deletes the authenticated user's reading progress row for an article.

        Args:
            db (AsyncSession): Active database session.
            user_id (uuid.UUID): Target learner unique identifier.
            article_id (uuid.UUID): Target article unique identifier.

        Raises:
            HTTPException: 404 if reading progress does not exist.

        Example:
            >>> # await ReadingService.delete_progress(db, user_id, article_id)
        """
        res = await db.execute(
            delete(UserArticleProgress).where(
                UserArticleProgress.user_id == user_id,
                UserArticleProgress.article_id == article_id,
            )
        )
        await db.commit()
        if res.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reading progress not found")

    @classmethod
    async def get_contextual_term(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        article_id: uuid.UUID,
        term_id: uuid.UUID,
        ai_service: Any | None = None,
    ) -> ContextualTermLookupDataDto:
        """Retrieves detailed lexical metadata for an active contextual term occurrence, lazily enriching with AI.

        Args:
            db (AsyncSession): Active database session.
            user_id (uuid.UUID): Target learner unique identifier.
            article_id (uuid.UUID): Target article unique identifier.
            term_id (uuid.UUID): Target vocabulary term unique identifier.
            ai_service (Any | None, optional): Custom AI service provider for testing. Defaults to None.

        Returns:
            ContextualTermLookupDataDto: Term lookup data including translation, examples, and save state.

        Raises:
            HTTPException: 404 if article or term is not found.
            HTTPException: 403 if lookup is disabled for the term.
            HTTPException: 503 if enrichment is processing or fails safely.

        Example:
            >>> # data = await ReadingService.get_contextual_term(db, user_id, article_id, term_id)
        """
        stmt = (
            select(ArticleSentenceTerm, ArticleSentence, Article)
            .join(ArticleSentence, ArticleSentenceTerm.sentence_id == ArticleSentence.id)
            .join(Article, ArticleSentence.article_id == Article.id)
            .where(
                ArticleSentenceTerm.id == term_id,
                Article.id == article_id,
                Article.status == ArticleStatus.PUBLISHED,
                ArticleSentence.content_version == Article.content_version,
                ArticleSentence.is_active.is_(True),
                ArticleSentenceTerm.is_active.is_(True),
                ArticleSentenceTerm.review_status == TermReviewStatus.APPROVED,
            )
        )
        res = await db.execute(stmt)
        row = res.first()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Published article or active current-version contextual term was not found",
            )
        term, sentence, article = row
        if not term.is_lookup_enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Contextual lookup is disabled for this term",
            )

        # Lazy AI Enrichment if not READY or if explanation fields are missing
        is_term_ready = (
            term.explanation_status == AiGenerationStatus.READY
            and term.contextual_meaning_vi is not None
            and term.part_of_speech is not None
        )

        if term.explanation_status == AiGenerationStatus.PROCESSING:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Contextual term enrichment is already processing; retry later",
            )

        if not is_term_ready:
            # Atomically claim enrichment rights
            claim_stmt = (
                update(ArticleSentenceTerm)
                .where(
                    ArticleSentenceTerm.id == term_id,
                    or_(
                        ArticleSentenceTerm.explanation_status.in_([AiGenerationStatus.PENDING, AiGenerationStatus.FAILED]),
                        ArticleSentenceTerm.contextual_meaning_vi.is_(None),
                        ArticleSentenceTerm.part_of_speech.is_(None),
                    ),
                )
                .values(explanation_status=AiGenerationStatus.PROCESSING)
            )
            claim_res = await db.execute(claim_stmt)
            await db.commit()

            if claim_res.rowcount == 0:
                # Re-query term: another worker claimed or finished
                re_term = await db.scalar(select(ArticleSentenceTerm).where(ArticleSentenceTerm.id == term_id))
                if (
                    re_term
                    and re_term.explanation_status == AiGenerationStatus.READY
                    and re_term.contextual_meaning_vi is not None
                ):
                    term = re_term
                else:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Contextual term enrichment is already processing; retry later",
                    )
            else:
                # Fetch surrounding sentences for context
                context_stmt = (
                    select(ArticleSentence)
                    .where(
                        ArticleSentence.article_id == article.id,
                        ArticleSentence.content_version == article.content_version,
                        ArticleSentence.is_active.is_(True),
                    )
                    .order_by(ArticleSentence.sentence_order.asc())
                )
                all_sentences = (await db.execute(context_stmt)).scalars().all()
                neighboring = [s for s in all_sentences if s.id != sentence.id]
                context_str = "\n".join(f"[{s.sentence_order}] {s.sentence_text[:1000]}" for s in neighboring)[
                    :4000
                ].strip()
                if not context_str:
                    context_str = sentence.sentence_text[:4000].strip()

                ai = ai_service or AiService()
                try:
                    enrichment_input = TermEnrichmentInput(
                        articleId=str(article.id),
                        articleTitle=article.title,
                        termId=str(term.id),
                        value=term.value,
                        lemma=term.lemma,
                        parentSentenceText=sentence.sentence_text,
                        surroundingSentenceContext=context_str,
                    )
                    enrichment = await ai.enrich_contextual_term(enrichment_input)

                    term.part_of_speech = enrichment.part_of_speech
                    term.cefr_level = enrichment.cefr_level
                    term.contextual_meaning_vi = enrichment.contextual_meaning_vi
                    term.definition_en = enrichment.definition_en
                    term.contextual_explanation = enrichment.contextual_explanation
                    term.ipa = enrichment.ipa
                    term.synonyms = enrichment.synonyms
                    term.antonyms = enrichment.antonyms
                    term.collocations = enrichment.collocations
                    term.related_terms = enrichment.related_terms
                    term.examples = [e.model_dump() for e in enrichment.examples]
                    term.explanation_status = AiGenerationStatus.READY
                    term.explanation_generated_at = datetime.now(UTC)
                    term.explanation_error = None

                    sentence.translation_vi = enrichment.sentence_translation_vi

                    await db.commit()
                    await db.refresh(term)
                    await db.refresh(sentence)
                except Exception as err:
                    term.explanation_status = AiGenerationStatus.FAILED
                    term.explanation_error = "AI contextual-term enrichment failed safely"
                    await db.commit()
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Contextual term enrichment is temporarily unavailable; retry later",
                    ) from err

        # Check if saved in user vocabularies
        save_stmt = select(UserVocabulary.id).where(
            UserVocabulary.user_id == user_id,
            UserVocabulary.article_sentence_term_id == term_id,
        )
        uv_id = (await db.execute(save_stmt)).scalar_one_or_none()

        # Parse examples safely
        raw_examples = term.examples
        if isinstance(raw_examples, list):
            examples = raw_examples
        elif isinstance(raw_examples, str):
            try:
                examples = json.loads(raw_examples)
            except Exception:
                examples = []
        else:
            examples = []

        term_dto = ContextualTermDto(
            id=term.id,
            value=term.value,
            lemma=term.lemma,
            partOfSpeech=term.part_of_speech,
            ipa=term.ipa,
            cefrLevel=term.cefr_level,
            contextualMeaningVi=term.contextual_meaning_vi,
            definitionEn=term.definition_en,
            contextualExplanation=term.contextual_explanation,
            explanationStatus=term.explanation_status,
            synonyms=term.synonyms or [],
            antonyms=term.antonyms or [],
            collocations=term.collocations or [],
            relatedTerms=term.related_terms or [],
            examples=examples,
        )

        parent_sentence_dto = ContextualParentSentenceDto(
            id=sentence.id,
            sentenceOrder=sentence.sentence_order,
            sentenceText=sentence.sentence_text,
            translationVi=sentence.translation_vi,
        )

        save_state_dto = ContextualTermSaveStateDto(
            isSaved=uv_id is not None,
            userVocabularyId=uv_id,
        )

        return ContextualTermLookupDataDto(
            term=term_dto,
            parentSentence=parent_sentence_dto,
            saveState=save_state_dto,
        )
