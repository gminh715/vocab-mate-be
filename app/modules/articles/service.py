"""Articles service implementing public catalog lookup, content parsing, CEFR analysis, and editorial workflows."""

import math
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.articles import Article, ArticleSentence, ArticleSentenceTerm
from app.models.categories import Category
from app.models.enums import AiGenerationStatus, ArticleStatus, CefrLevel, TermOrigin, TermReviewStatus
from app.models.vocabularies import UserVocabulary
from app.modules.articles.helpers.cefr_analyzer import CefrAnalyzerHelper
from app.modules.articles.helpers.html_sanitizer import HtmlSanitizerHelper
from app.modules.articles.helpers.sentence_parser import SentenceParserHelper
from app.modules.articles.helpers.term_marker import TermMarkerHelper
from app.modules.articles.schemas import (
    AdminArticleDetailDataDto,
    AdminArticleDto,
    AdminArticleListItemDto,
    AdminArticleSentenceDetailDto,
    AdminArticleSentenceItemDto,
    AdminArticleTermDetailDto,
    ArticleAnalysisDataDto,
    ArticleArchiveDataDto,
    ArticleDetailDataDto,
    ArticleMutationDataDto,
    ArticlePublishDataDto,
    ArticleRestoreDraftDataDto,
    ArticleSentenceDto,
    ArticleSentenceTermDto,
    ArticleTermMutationDataDto,
    ArticleUpdateDataDto,
    CreateArticleDto,
    CreateArticleTermDto,
    ParseArticleContentDataDto,
    ParseArticleContentDto,
    PublicArticleCardDto,
    PublicArticleMetadataDto,
    PublicCategoryDto,
    UpdateArticleDto,
    UpdateArticleSentenceDto,
    UpdateArticleTermDto,
)


class ArticlesService:
    """Service managing public catalog discovery and administrative curation of articles.

    Example:
        >>> # service = ArticlesService
    """

    @classmethod
    async def find_all_published(
        cls,
        db: AsyncSession,
        page: int = 1,
        limit: int = 20,
        q: str | None = None,
        category_id: uuid.UUID | None = None,
        cefr_level: CefrLevel | None = None,
        sort: str = "newest",
    ) -> tuple[list[PublicArticleCardDto], dict]:
        """Lists published articles with pagination and filters.

        Args:
            db (AsyncSession): Active database session.
            page (int, optional): 1-indexed page number. Defaults to 1.
            limit (int, optional): Items per page limit. Defaults to 20.
            q (str | None, optional): Search query on article title. Defaults to None.
            category_id (uuid.UUID | None, optional): Category identifier filter. Defaults to None.
            cefr_level (CefrLevel | None, optional): Target CEFR difficulty level filter. Defaults to None.
            sort (str, optional): Sort order ('newest' or 'oldest'). Defaults to 'newest'.

        Returns:
            tuple[list[PublicArticleCardDto], dict]: List of public article cards and pagination metadata.

        Example:
            >>> # items, meta = await ArticlesService.find_all_published(db, page=1, limit=10)
        """
        stmt = select(Article).options(selectinload(Article.category)).where(Article.status == ArticleStatus.PUBLISHED)
        count_stmt = select(func.count()).select_from(Article).where(Article.status == ArticleStatus.PUBLISHED)

        if category_id:
            stmt = stmt.where(Article.category_id == category_id)
            count_stmt = count_stmt.where(Article.category_id == category_id)

        if cefr_level:
            stmt = stmt.where(Article.cefr_level == cefr_level)
            count_stmt = count_stmt.where(Article.cefr_level == cefr_level)

        if q and q.strip():
            term = f"%{q.strip()}%"
            stmt = stmt.where(Article.title.ilike(term))
            count_stmt = count_stmt.where(Article.title.ilike(term))

        total_res = await db.execute(count_stmt)
        total = total_res.scalar_one()

        if sort == "oldest":
            stmt = stmt.order_by(Article.published_at.asc(), Article.id.asc())
        else:
            stmt = stmt.order_by(Article.published_at.desc(), Article.id.desc())

        offset = (page - 1) * limit
        stmt = stmt.offset(offset).limit(limit)
        res = await db.execute(stmt)
        articles = res.scalars().all()

        items = [
            PublicArticleCardDto(
                id=a.id,
                title=a.title,
                slug=a.slug,
                summary=a.summary,
                thumbnailUrl=a.thumbnail_url,
                cefrLevel=a.cefr_level,
                publishedAt=a.published_at,
                category=PublicCategoryDto.model_validate(a.category),
            )
            for a in articles
        ]
        meta = {
            "page": page,
            "limit": limit,
            "total": total,
            "totalPages": math.ceil(total / limit) if limit > 0 else 0,
        }
        return items, meta

    @classmethod
    async def find_one_by_slug(cls, db: AsyncSession, slug: str) -> ArticleDetailDataDto:
        """Retrieves public metadata and category for a single published article by slug.

        Args:
            db (AsyncSession): Active database session.
            slug (str): Normalized article slug.

        Returns:
            ArticleDetailDataDto: Public article detail metadata and category payload.

        Raises:
            HTTPException: 404 if article not found or not published.

        Example:
            >>> # detail = await ArticlesService.find_one_by_slug(db, "sample-slug")
        """
        stmt = (
            select(Article)
            .options(selectinload(Article.category))
            .where(Article.slug == slug.strip().lower(), Article.status == ArticleStatus.PUBLISHED)
        )
        res = await db.execute(stmt)
        article = res.scalar_one_or_none()
        if not article:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")

        return ArticleDetailDataDto(
            article=PublicArticleMetadataDto.model_validate(article),
            category=PublicCategoryDto.model_validate(article.category),
        )

    @classmethod
    async def find_all_admin(
        cls,
        db: AsyncSession,
        page: int = 1,
        limit: int = 20,
        q: str | None = None,
        category_id: uuid.UUID | None = None,
        cefr_level: CefrLevel | None = None,
        article_status: ArticleStatus | None = None,
        sort: str = "newest",
    ) -> tuple[list[AdminArticleListItemDto], dict]:
        """Lists articles across all statuses for administrators.

        Args:
            db (AsyncSession): Active database session.
            page (int, optional): 1-indexed page number. Defaults to 1.
            limit (int, optional): Items per page. Defaults to 20.
            q (str | None, optional): Search query on article title. Defaults to None.
            category_id (uuid.UUID | None, optional): Filter by category. Defaults to None.
            cefr_level (CefrLevel | None, optional): Filter by CEFR level. Defaults to None.
            article_status (ArticleStatus | None, optional): Filter by article lifecycle status. Defaults to None.
            sort (str, optional): Sort order ('newest' or 'oldest'). Defaults to 'newest'.

        Returns:
            tuple[list[AdminArticleListItemDto], dict]: List of admin article items and pagination metadata.

        Example:
            >>> # items, meta = await ArticlesService.find_all_admin(db, page=1, limit=20)
        """
        stmt = select(Article).options(selectinload(Article.category))
        count_stmt = select(func.count()).select_from(Article)

        if category_id:
            stmt = stmt.where(Article.category_id == category_id)
            count_stmt = count_stmt.where(Article.category_id == category_id)

        if cefr_level:
            stmt = stmt.where(Article.cefr_level == cefr_level)
            count_stmt = count_stmt.where(Article.cefr_level == cefr_level)

        if article_status:
            stmt = stmt.where(Article.status == article_status)
            count_stmt = count_stmt.where(Article.status == article_status)

        if q and q.strip():
            term = f"%{q.strip()}%"
            stmt = stmt.where(Article.title.ilike(term))
            count_stmt = count_stmt.where(Article.title.ilike(term))

        total_res = await db.execute(count_stmt)
        total = total_res.scalar_one()

        if sort == "oldest":
            stmt = stmt.order_by(Article.created_at.asc(), Article.id.asc())
        else:
            stmt = stmt.order_by(Article.created_at.desc(), Article.id.desc())

        offset = (page - 1) * limit
        stmt = stmt.offset(offset).limit(limit)
        res = await db.execute(stmt)
        articles = res.scalars().all()

        items = [
            AdminArticleListItemDto(
                id=a.id,
                categoryId=a.category_id,
                title=a.title,
                slug=a.slug,
                summary=a.summary,
                thumbnailUrl=a.thumbnail_url,
                cefrLevel=a.cefr_level,
                status=a.status,
                contentVersion=a.content_version,
                externalId=a.external_id,
                sourcePublishedAt=a.source_published_at,
                aiAnalysisStatus=a.ai_analysis_status,
                aiAnalysisError=a.ai_analysis_error,
                publishedAt=a.published_at,
                archivedAt=a.archived_at,
                createdAt=a.created_at,
                updatedAt=a.updated_at,
                category=PublicCategoryDto.model_validate(a.category),
            )
            for a in articles
        ]
        meta = {
            "page": page,
            "limit": limit,
            "total": total,
            "totalPages": math.ceil(total / limit) if limit > 0 else 0,
        }
        return items, meta

    @classmethod
    async def find_one_admin(cls, db: AsyncSession, article_id: uuid.UUID) -> AdminArticleDetailDataDto:
        """Retrieves administrative article detail along with sentence and term counts.

        Args:
            db (AsyncSession): Active database session.
            article_id (uuid.UUID): Target article identifier.

        Returns:
            AdminArticleDetailDataDto: Article detail with sentence and term counts.

        Raises:
            HTTPException: 404 if article not found.

        Example:
            >>> # detail = await ArticlesService.find_one_admin(db, article_id)
        """
        stmt = select(Article).options(selectinload(Article.category)).where(Article.id == article_id)
        res = await db.execute(stmt)
        article = res.scalar_one_or_none()
        if not article:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")

        s_count_res = await db.execute(
            select(func.count()).select_from(ArticleSentence).where(ArticleSentence.article_id == article_id)
        )
        sentence_count = s_count_res.scalar_one()

        t_count_res = await db.execute(
            select(func.count())
            .select_from(ArticleSentenceTerm)
            .join(ArticleSentence, ArticleSentenceTerm.sentence_id == ArticleSentence.id)
            .where(ArticleSentence.article_id == article_id)
        )
        term_count = t_count_res.scalar_one()

        return AdminArticleDetailDataDto(
            article=AdminArticleDto.model_validate(article),
            sentenceCount=sentence_count,
            termCount=term_count,
        )

    @classmethod
    async def create(
        cls,
        db: AsyncSession,
        acting_admin_id: uuid.UUID,
        dto: CreateArticleDto,
    ) -> ArticleMutationDataDto:
        """Creates a new draft article with initial content version 1 and sanitized HTML content.

        Args:
            db (AsyncSession): Active database session.
            acting_admin_id (uuid.UUID): Administrator performing the creation.
            dto (CreateArticleDto): Article creation payload.

        Returns:
            ArticleMutationDataDto: Created article admin representation.

        Raises:
            HTTPException: 400 if category is inactive, 404 if category not found, 409 if slug conflict.

        Example:
            >>> # res = await ArticlesService.create(db, admin_id, dto)
        """
        # Verify category exists and is active
        cat_stmt = select(Category).where(Category.id == dto.categoryId)
        cat_res = await db.execute(cat_stmt)
        category = cat_res.scalar_one_or_none()
        if not category:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
        if not category.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot assign inactive category")

        clean_html = HtmlSanitizerHelper.sanitize(dto.contentHtml)
        article = Article(
            id=uuid.uuid4(),
            category_id=dto.categoryId,
            title=dto.title.strip(),
            slug=dto.slug.strip().lower(),
            summary=dto.summary.strip(),
            content_html=clean_html,
            content_version=1,
            cefr_level=dto.cefrLevel,
            status=ArticleStatus.DRAFT,
            source_name=dto.sourceName.strip() if dto.sourceName else None,
            source_url=dto.sourceUrl.strip() if dto.sourceUrl else None,
            author_name=dto.authorName.strip() if dto.authorName else None,
            thumbnail_url=dto.thumbnailUrl.strip() if dto.thumbnailUrl else None,
        )
        db.add(article)
        try:
            await db.commit()
            await db.refresh(article)
        except IntegrityError as err:
            await db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Article slug already exists") from err

        article.category = category
        return ArticleMutationDataDto(article=AdminArticleDto.model_validate(article))

    @classmethod
    async def update(
        cls,
        db: AsyncSession,
        acting_admin_id: uuid.UUID,
        article_id: uuid.UUID,
        dto: UpdateArticleDto,
    ) -> ArticleUpdateDataDto:
        """Partially updates article metadata and content.

        Args:
            db (AsyncSession): Active database session.
            acting_admin_id (uuid.UUID): Administrator performing the update.
            article_id (uuid.UUID): Target article identifier.
            dto (UpdateArticleDto): Article partial update payload.

        Returns:
            ArticleUpdateDataDto: Updated article admin representation and contentChanged flag.

        Raises:
            HTTPException: 400 if assigned category is inactive, 404 if article or category not found, 409 on slug conflict.

        Example:
            >>> # res = await ArticlesService.update(db, admin_id, article_id, dto)
        """
        stmt = select(Article).options(selectinload(Article.category)).where(Article.id == article_id)
        res = await db.execute(stmt)
        article = res.scalar_one_or_none()
        if not article:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")

        content_changed = False
        if dto.categoryId is not None and dto.categoryId != article.category_id:
            cat_stmt = select(Category).where(Category.id == dto.categoryId)
            cat_res = await db.execute(cat_stmt)
            category = cat_res.scalar_one_or_none()
            if not category or not category.is_active:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Active category not found")
            article.category_id = dto.categoryId
            article.category = category

        if dto.title is not None:
            article.title = dto.title.strip()
        if dto.slug is not None:
            article.slug = dto.slug.strip().lower()
        if dto.summary is not None:
            article.summary = dto.summary.strip()
        if dto.cefrLevel is not None:
            article.cefr_level = dto.cefrLevel
        if dto.sourceName is not None:
            article.source_name = dto.sourceName.strip()
        if dto.sourceUrl is not None:
            article.source_url = dto.sourceUrl.strip()
        if dto.authorName is not None:
            article.author_name = dto.authorName.strip()
        if dto.thumbnailUrl is not None:
            article.thumbnail_url = dto.thumbnailUrl.strip()

        if dto.contentHtml is not None:
            sanitized = HtmlSanitizerHelper.sanitize(dto.contentHtml)
            if sanitized != article.content_html:
                content_changed = True
                article.content_html = sanitized
                # Invalidate parsed sentences if content changed
                sentence_ids_subquery = select(ArticleSentence.id).where(ArticleSentence.article_id == article_id)
                await db.execute(
                    delete(ArticleSentenceTerm).where(ArticleSentenceTerm.sentence_id.in_(sentence_ids_subquery))
                )
                await db.execute(delete(ArticleSentence).where(ArticleSentence.article_id == article_id))
                article.ai_analysis_status = None

        try:
            await db.commit()
            await db.refresh(article)
        except IntegrityError as err:
            await db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Article slug already exists") from err

        return ArticleUpdateDataDto(article=AdminArticleDto.model_validate(article), contentChanged=content_changed)

    @classmethod
    async def parse_content(
        cls,
        db: AsyncSession,
        acting_admin_id: uuid.UUID,
        article_id: uuid.UUID,
        dto: ParseArticleContentDto | None = None,
    ) -> ParseArticleContentDataDto:
        """Parses raw article HTML into segmented sentence records and inserts data-sentence-id markers.

        Args:
            db (AsyncSession): Active database session.
            acting_admin_id (uuid.UUID): Administrator performing the parsing.
            article_id (uuid.UUID): Target article identifier.
            dto (ParseArticleContentDto | None, optional): Parsing options payload. Defaults to None.

        Returns:
            ParseArticleContentDataDto: Parsing result containing contentVersion, sentenceCount, and marked HTML.

        Raises:
            HTTPException: 404 if article not found, 422 if no readable sentences found.

        Example:
            >>> # res = await ArticlesService.parse_content(db, admin_id, article_id, dto)
        """
        stmt = select(Article).where(Article.id == article_id)
        res = await db.execute(stmt)
        article = res.scalar_one_or_none()
        if not article:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")

        # Parse sentences
        parsed = SentenceParserHelper.parse(article.content_html)
        if not parsed.sentences:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No readable sentences found")

        # Delete existing terms & sentences
        sentence_ids_subquery = select(ArticleSentence.id).where(ArticleSentence.article_id == article_id)
        await db.execute(delete(ArticleSentenceTerm).where(ArticleSentenceTerm.sentence_id.in_(sentence_ids_subquery)))
        await db.execute(delete(ArticleSentence).where(ArticleSentence.article_id == article_id))

        # Add new sentences
        for s in parsed.sentences:
            db.add(
                ArticleSentence(
                    id=s.id,
                    article_id=article_id,
                    content_version=article.content_version,
                    sentence_order=s.sentence_order,
                    sentence_text=s.sentence_text,
                )
            )

        article.content_html = parsed.content_html
        await db.commit()
        await db.refresh(article)

        return ParseArticleContentDataDto(
            contentVersion=article.content_version,
            sentenceCount=len(parsed.sentences),
            contentHtml=article.content_html,
        )

    @classmethod
    async def analyze(
        cls,
        db: AsyncSession,
        acting_admin_id: uuid.UUID,
        article_id: uuid.UUID,
    ) -> ArticleAnalysisDataDto:
        """Executes local CEFR lexical analysis and extracts candidate vocabulary terms for the parsed draft.

        Args:
            db (AsyncSession): Active database session.
            acting_admin_id (uuid.UUID): Administrator triggering the analysis.
            article_id (uuid.UUID): Target article identifier.

        Returns:
            ArticleAnalysisDataDto: Analysis output with evaluated CEFR level and candidate count.

        Raises:
            HTTPException: 404 if article not found, 422 if article has not been parsed into sentences.

        Example:
            >>> # res = await ArticlesService.analyze(db, admin_id, article_id)
        """
        stmt = select(Article).options(selectinload(Article.category)).where(Article.id == article_id)
        res = await db.execute(stmt)
        article = res.scalar_one_or_none()
        if not article:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")

        s_stmt = (
            select(ArticleSentence)
            .where(ArticleSentence.article_id == article_id)
            .order_by(ArticleSentence.sentence_order.asc())
        )
        s_res = await db.execute(s_stmt)
        sentences = s_res.scalars().all()
        if not sentences:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Article must be parsed into sentences before analysis",
            )

        # Combine text for article-level CEFR rating
        full_text = " ".join(s.sentence_text for s in sentences)
        evaluated_cefr, term_levels, _ = CefrAnalyzerHelper.evaluate_text(full_text)
        article.cefr_level = evaluated_cefr

        # Extract and mark candidate vocabulary terms (B1, B2, C1, C2)
        target_levels = {CefrLevel.B1, CefrLevel.B2, CefrLevel.C1, CefrLevel.C2}
        content_html = article.content_html
        candidate_count = 0

        # Delete old terms
        sentence_ids_subquery = select(ArticleSentence.id).where(ArticleSentence.article_id == article_id)
        await db.execute(delete(ArticleSentenceTerm).where(ArticleSentenceTerm.sentence_id.in_(sentence_ids_subquery)))

        for s in sentences:
            s_level, s_term_levels, _ = CefrAnalyzerHelper.evaluate_text(s.sentence_text)
            seen_words: set[str] = set()
            for word, lvl in s_term_levels.items():
                if (
                    lvl in target_levels
                    and word not in seen_words
                    and TermMarkerHelper.matches_text(s.sentence_text, word)
                ):
                    seen_words.add(word)
                    t_id = uuid.uuid4()
                    db.add(
                        ArticleSentenceTerm(
                            id=t_id,
                            sentence_id=s.id,
                            value=word,
                            lemma=word.lower(),
                            cefr_level=lvl,
                            origin=TermOrigin.NLP,
                            review_status=TermReviewStatus.APPROVED,
                            explanation_status=AiGenerationStatus.READY,
                            is_lookup_enabled=True,
                            is_active=True,
                        )
                    )
                    content_html = TermMarkerHelper.insert(content_html, s.id, t_id, word)
                    candidate_count += 1

        category_dto = PublicCategoryDto.model_validate(article.category)
        article.content_html = content_html
        article.ai_analysis_status = AiGenerationStatus.READY
        await db.commit()
        await db.refresh(article)

        return ArticleAnalysisDataDto(
            articleId=article.id,
            contentVersion=article.content_version,
            aiAnalysisStatus=AiGenerationStatus.READY,
            category=category_dto,
            cefrLevel=article.cefr_level,
            candidateCount=candidate_count,
        )

    @classmethod
    async def publish(
        cls,
        db: AsyncSession,
        acting_admin_id: uuid.UUID,
        article_id: uuid.UUID,
    ) -> ArticlePublishDataDto:
        """Validates article publication invariants and transitions the draft to PUBLISHED status.

        Args:
            db (AsyncSession): Active database session.
            acting_admin_id (uuid.UUID): Administrator performing publication.
            article_id (uuid.UUID): Target article identifier.

        Returns:
            ArticlePublishDataDto: Published status and publication timestamp.

        Raises:
            HTTPException: 404 if article not found, 422 if article lacks parsed sentences.

        Example:
            >>> # res = await ArticlesService.publish(db, admin_id, article_id)
        """
        stmt = select(Article).where(Article.id == article_id)
        res = await db.execute(stmt)
        article = res.scalar_one_or_none()
        if not article:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")

        # Publication checklist:
        # 1. Must have parsed sentences
        s_count_res = await db.execute(
            select(func.count()).select_from(ArticleSentence).where(ArticleSentence.article_id == article_id)
        )
        if s_count_res.scalar_one() == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Article must have parsed sentences before publishing",
            )

        now = datetime.now(UTC)
        article.status = ArticleStatus.PUBLISHED
        article.published_at = now
        await db.commit()
        await db.refresh(article)

        return ArticlePublishDataDto(id=article.id, status=article.status, publishedAt=article.published_at)

    @classmethod
    async def archive(
        cls,
        db: AsyncSession,
        acting_admin_id: uuid.UUID,
        article_id: uuid.UUID,
    ) -> ArticleArchiveDataDto:
        """Transitions an article to ARCHIVED status.

        Args:
            db (AsyncSession): Active database session.
            acting_admin_id (uuid.UUID): Administrator performing archival.
            article_id (uuid.UUID): Target article identifier.

        Returns:
            ArticleArchiveDataDto: Archived status and timestamp.

        Raises:
            HTTPException: 404 if article not found.

        Example:
            >>> # res = await ArticlesService.archive(db, admin_id, article_id)
        """
        stmt = select(Article).where(Article.id == article_id)
        res = await db.execute(stmt)
        article = res.scalar_one_or_none()
        if not article:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")

        now = datetime.now(UTC)
        article.status = ArticleStatus.ARCHIVED
        article.archived_at = now
        await db.commit()
        await db.refresh(article)

        return ArticleArchiveDataDto(id=article.id, status=article.status, archivedAt=article.archived_at)

    @classmethod
    async def restore_draft(
        cls,
        db: AsyncSession,
        acting_admin_id: uuid.UUID,
        article_id: uuid.UUID,
    ) -> ArticleRestoreDraftDataDto:
        """Restores an archived article to DRAFT status.

        Args:
            db (AsyncSession): Active database session.
            acting_admin_id (uuid.UUID): Administrator performing restoration.
            article_id (uuid.UUID): Target article identifier.

        Returns:
            ArticleRestoreDraftDataDto: Restored DRAFT status response.

        Raises:
            HTTPException: 404 if article not found, 409 if article is not in ARCHIVED status.

        Example:
            >>> # res = await ArticlesService.restore_draft(db, admin_id, article_id)
        """
        stmt = select(Article).where(Article.id == article_id)
        res = await db.execute(stmt)
        article = res.scalar_one_or_none()
        if not article:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
        if article.status != ArticleStatus.ARCHIVED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only an archived article can be restored")

        article.status = ArticleStatus.DRAFT
        article.published_at = None
        article.archived_at = None
        await db.commit()
        await db.refresh(article)

        return ArticleRestoreDraftDataDto(id=article.id, status=article.status)

    # -----------------------------------------------------------------------
    # Admin Article Sentences Methods
    # -----------------------------------------------------------------------

    @classmethod
    async def get_admin_sentences(
        cls,
        db: AsyncSession,
        article_id: uuid.UUID,
        page: int = 1,
        limit: int = 20,
        is_active: bool | None = None,
    ) -> tuple[list[AdminArticleSentenceItemDto], dict]:
        """Lists current-version sentences with pagination ordered by sentenceOrder.

        Args:
            db (AsyncSession): Active database session.
            article_id (uuid.UUID): Target article identifier.
            page (int, optional): 1-indexed page number. Defaults to 1.
            limit (int, optional): Items per page. Defaults to 20.
            is_active (bool | None, optional): Filter by sentence active flag. Defaults to None.

        Returns:
            tuple[list[AdminArticleSentenceItemDto], dict]: List of sentence items and pagination meta.

        Raises:
            HTTPException: 404 if article not found.

        Example:
            >>> # items, meta = await ArticlesService.get_admin_sentences(db, article_id, page=1, limit=20)
        """
        article_res = await db.execute(select(Article).where(Article.id == article_id))
        article = article_res.scalar_one_or_none()
        if not article:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")

        stmt = select(ArticleSentence).where(
            ArticleSentence.article_id == article_id,
            ArticleSentence.content_version == article.content_version,
        )
        count_stmt = (
            select(func.count())
            .select_from(ArticleSentence)
            .where(
                ArticleSentence.article_id == article_id,
                ArticleSentence.content_version == article.content_version,
            )
        )

        if is_active is not None:
            stmt = stmt.where(ArticleSentence.is_active == is_active)
            count_stmt = count_stmt.where(ArticleSentence.is_active == is_active)

        total_res = await db.execute(count_stmt)
        total = total_res.scalar_one()

        stmt = stmt.order_by(ArticleSentence.sentence_order.asc())
        offset = (page - 1) * limit
        stmt = stmt.offset(offset).limit(limit)

        res = await db.execute(stmt)
        sentences = res.scalars().all()

        # Query term counts per sentence in one batch
        if sentences:
            s_ids = [s.id for s in sentences]
            tc_stmt = (
                select(ArticleSentenceTerm.sentence_id, func.count())
                .where(ArticleSentenceTerm.sentence_id.in_(s_ids))
                .group_by(ArticleSentenceTerm.sentence_id)
            )
            tc_res = await db.execute(tc_stmt)
            term_counts = dict(tc_res.all())
        else:
            term_counts = {}

        items = [
            AdminArticleSentenceItemDto(
                id=s.id,
                articleId=s.article_id,
                contentVersion=s.content_version,
                sentenceOrder=s.sentence_order,
                sentenceText=s.sentence_text,
                translationVi=s.translation_vi,
                isActive=s.is_active,
                createdAt=s.created_at,
                updatedAt=s.updated_at,
                termCount=term_counts.get(s.id, 0),
            )
            for s in sentences
        ]
        meta = {
            "page": page,
            "limit": limit,
            "total": total,
            "totalPages": math.ceil(total / limit) if limit > 0 else 0,
        }
        return items, meta, article.content_version

    @classmethod
    async def get_admin_sentence(
        cls,
        db: AsyncSession,
        article_id: uuid.UUID,
        sentence_id: uuid.UUID,
    ) -> AdminArticleSentenceDetailDto:
        """Retrieves a single current-version sentence and its associated terms.

        Args:
            db (AsyncSession): Active database session.
            article_id (uuid.UUID): Target article identifier.
            sentence_id (uuid.UUID): Target sentence identifier.

        Returns:
            AdminArticleSentenceDetailDto: Sentence detail with terms list.

        Raises:
            HTTPException: 404 if sentence not found.

        Example:
            >>> # sentence = await ArticlesService.get_admin_sentence(db, article_id, sentence_id)
        """
        stmt = (
            select(ArticleSentence)
            .options(selectinload(ArticleSentence.terms))
            .where(
                ArticleSentence.id == sentence_id,
                ArticleSentence.article_id == article_id,
            )
        )
        res = await db.execute(stmt)
        sentence = res.scalar_one_or_none()
        if not sentence:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sentence not found")

        terms_dto = [ArticleSentenceTermDto.model_validate(t) for t in sentence.terms]
        return AdminArticleSentenceDetailDto(
            id=sentence.id,
            articleId=sentence.article_id,
            contentVersion=sentence.content_version,
            sentenceOrder=sentence.sentence_order,
            sentenceText=sentence.sentence_text,
            translationVi=sentence.translation_vi,
            isActive=sentence.is_active,
            createdAt=sentence.created_at,
            updatedAt=sentence.updated_at,
            terms=terms_dto,
        )

    @classmethod
    async def update_admin_sentence(
        cls,
        db: AsyncSession,
        acting_admin_id: uuid.UUID,
        article_id: uuid.UUID,
        sentence_id: uuid.UUID,
        dto: UpdateArticleSentenceDto,
    ) -> ArticleSentenceDto:
        """Updates Vietnamese translation or active flag of a current-version sentence.

        Args:
            db (AsyncSession): Active database session.
            acting_admin_id (uuid.UUID): Administrator performing the action.
            article_id (uuid.UUID): Target article identifier.
            sentence_id (uuid.UUID): Target sentence identifier.
            dto (UpdateArticleSentenceDto): Fields to update.

        Returns:
            ArticleSentenceDto: Updated sentence entity.

        Raises:
            HTTPException: 404 if sentence not found; 409 if article is archived.

        Example:
            >>> # updated = await ArticlesService.update_admin_sentence(db, admin_id, article_id, s_id, dto)
        """
        art_res = await db.execute(select(Article).where(Article.id == article_id))
        art = art_res.scalar_one_or_none()
        if not art:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
        if art.status == ArticleStatus.ARCHIVED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Archived articles cannot be modified")

        stmt = select(ArticleSentence).where(
            ArticleSentence.id == sentence_id,
            ArticleSentence.article_id == article_id,
        )
        res = await db.execute(stmt)
        sentence = res.scalar_one_or_none()
        if not sentence:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sentence not found")

        if dto.translationVi is not None:
            sentence.translation_vi = dto.translationVi.strip()
        if dto.isActive is not None:
            sentence.is_active = dto.isActive

        await db.commit()
        await db.refresh(sentence)
        return ArticleSentenceDto.model_validate(sentence)

    # -----------------------------------------------------------------------
    # Admin Article Terms Methods
    # -----------------------------------------------------------------------

    @classmethod
    async def create_admin_term(
        cls,
        db: AsyncSession,
        acting_admin_id: uuid.UUID,
        article_id: uuid.UUID,
        sentence_id: uuid.UUID,
        dto: CreateArticleTermDto,
    ) -> ArticleTermMutationDataDto:
        """Manually creates a new vocabulary term and wraps it in HTML markers.

        Args:
            db (AsyncSession): Active database session.
            acting_admin_id (uuid.UUID): Administrator performing the action.
            article_id (uuid.UUID): Target article identifier.
            sentence_id (uuid.UUID): Target sentence identifier.
            dto (CreateArticleTermDto): Term creation payload.

        Returns:
            ArticleTermMutationDataDto: Newly created term entity and mutation confirmation.

        Raises:
            HTTPException: 404 if article/sentence not found; 409 if article archived or sentence inactive;
                           422 if term value does not match sentence text.

        Example:
            >>> # res = await ArticlesService.create_admin_term(db, admin_id, art_id, s_id, term_dto)
        """
        art_res = await db.execute(select(Article).where(Article.id == article_id))
        article = art_res.scalar_one_or_none()
        if not article:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
        if article.status == ArticleStatus.ARCHIVED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Archived articles cannot be modified")

        s_res = await db.execute(
            select(ArticleSentence).where(
                ArticleSentence.id == sentence_id,
                ArticleSentence.article_id == article_id,
            )
        )
        sentence = s_res.scalar_one_or_none()
        if not sentence:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sentence not found")
        if not sentence.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Terms cannot be added to an inactive sentence"
            )

        if not TermMarkerHelper.matches_text(sentence.sentence_text, dto.value):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Term value does not occur in target sentence text",
            )

        term_id = uuid.uuid4()
        updated_html = TermMarkerHelper.insert(article.content_html, sentence_id, term_id, dto.value)
        content_changed = updated_html != article.content_html
        if content_changed:
            article.content_html = updated_html

        new_term = ArticleSentenceTerm(
            id=term_id,
            sentence_id=sentence_id,
            value=dto.value,
            lemma=dto.lemma,
            part_of_speech=dto.partOfSpeech,
            ipa=dto.ipa,
            cefr_level=dto.cefrLevel,
            contextual_meaning_vi=dto.contextualMeaningVi,
            definition_en=dto.definitionEn,
            contextual_explanation=dto.contextualExplanation,
            synonyms=dto.synonyms,
            antonyms=dto.antonyms,
            collocations=dto.collocations,
            related_terms=dto.relatedTerms,
            examples=dto.examples,
            origin=TermOrigin.MANUAL,
            review_status=TermReviewStatus.APPROVED,
            explanation_status=AiGenerationStatus.READY,
            is_lookup_enabled=True,
            is_active=True,
        )
        db.add(new_term)
        await db.commit()
        await db.refresh(new_term)

        return ArticleTermMutationDataDto(
            term=ArticleSentenceTermDto.model_validate(new_term),
            contentHtmlChanged=content_changed,
        )

    @classmethod
    async def get_admin_terms(
        cls,
        db: AsyncSession,
        article_id: uuid.UUID,
        page: int = 1,
        limit: int = 20,
        sentence_id: uuid.UUID | None = None,
        cefr_level: CefrLevel | None = None,
        origin: TermOrigin | None = None,
        review_status: TermReviewStatus | None = None,
        explanation_status: AiGenerationStatus | None = None,
        is_active: bool | None = None,
        q: str | None = None,
    ) -> tuple[list[ArticleSentenceTermDto], dict]:
        """Lists contextual terms for an article with multiple filtering criteria.

        Args:
            db (AsyncSession): Active database session.
            article_id (uuid.UUID): Target article identifier.
            page (int, optional): Current page number. Defaults to 1.
            limit (int, optional): Page item limit. Defaults to 20.
            sentence_id (uuid.UUID | None, optional): Filter by sentence. Defaults to None.
            cefr_level (CefrLevel | None, optional): Filter by CEFR level. Defaults to None.
            origin (TermOrigin | None, optional): Filter by origin (MANUAL, AI, NLP). Defaults to None.
            review_status (TermReviewStatus | None, optional): Filter by review status. Defaults to None.
            explanation_status (AiGenerationStatus | None, optional): Filter by explanation state. Defaults to None.
            is_active (bool | None, optional): Filter by active state. Defaults to None.
            q (str | None, optional): Text search query over value and lemma. Defaults to None.

        Returns:
            tuple[list[ArticleSentenceTermDto], dict]: List of term entities and pagination metadata.

        Raises:
            HTTPException: 404 if article not found.

        Example:
            >>> # terms, meta = await ArticlesService.get_admin_terms(db, article_id, page=1)
        """
        art_res = await db.execute(select(Article).where(Article.id == article_id))
        article = art_res.scalar_one_or_none()
        if not article:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")

        sentence_ids_subquery = select(ArticleSentence.id).where(
            ArticleSentence.article_id == article_id,
            ArticleSentence.content_version == article.content_version,
        )

        stmt = select(ArticleSentenceTerm).where(ArticleSentenceTerm.sentence_id.in_(sentence_ids_subquery))
        count_stmt = (
            select(func.count())
            .select_from(ArticleSentenceTerm)
            .where(ArticleSentenceTerm.sentence_id.in_(sentence_ids_subquery))
        )

        if sentence_id is not None:
            stmt = stmt.where(ArticleSentenceTerm.sentence_id == sentence_id)
            count_stmt = count_stmt.where(ArticleSentenceTerm.sentence_id == sentence_id)
        if cefr_level is not None:
            stmt = stmt.where(ArticleSentenceTerm.cefr_level == cefr_level)
            count_stmt = count_stmt.where(ArticleSentenceTerm.cefr_level == cefr_level)
        if origin is not None:
            stmt = stmt.where(ArticleSentenceTerm.origin == origin)
            count_stmt = count_stmt.where(ArticleSentenceTerm.origin == origin)
        if review_status is not None:
            stmt = stmt.where(ArticleSentenceTerm.review_status == review_status)
            count_stmt = count_stmt.where(ArticleSentenceTerm.review_status == review_status)
        if explanation_status is not None:
            stmt = stmt.where(ArticleSentenceTerm.explanation_status == explanation_status)
            count_stmt = count_stmt.where(ArticleSentenceTerm.explanation_status == explanation_status)
        if is_active is not None:
            stmt = stmt.where(ArticleSentenceTerm.is_active == is_active)
            count_stmt = count_stmt.where(ArticleSentenceTerm.is_active == is_active)
        if q and q.strip():
            term_q = f"%{q.strip()}%"
            stmt = stmt.where(ArticleSentenceTerm.value.ilike(term_q) | ArticleSentenceTerm.lemma.ilike(term_q))
            count_stmt = count_stmt.where(
                ArticleSentenceTerm.value.ilike(term_q) | ArticleSentenceTerm.lemma.ilike(term_q)
            )

        total_res = await db.execute(count_stmt)
        total = total_res.scalar_one()

        stmt = stmt.order_by(ArticleSentenceTerm.created_at.desc())
        offset = (page - 1) * limit
        stmt = stmt.offset(offset).limit(limit)

        res = await db.execute(stmt)
        terms = res.scalars().all()

        items = [ArticleSentenceTermDto.model_validate(t) for t in terms]
        meta = {
            "page": page,
            "limit": limit,
            "total": total,
            "totalPages": math.ceil(total / limit) if limit > 0 else 0,
        }
        return items, meta, article.content_version

    @classmethod
    async def get_admin_term(
        cls,
        db: AsyncSession,
        article_id: uuid.UUID,
        term_id: uuid.UUID,
    ) -> AdminArticleTermDetailDto:
        """Retrieves details of a contextual term and its parent sentence.

        Args:
            db (AsyncSession): Active database session.
            article_id (uuid.UUID): Target article identifier.
            term_id (uuid.UUID): Target term identifier.

        Returns:
            AdminArticleTermDetailDto: Contextual term with parent sentence metadata.

        Raises:
            HTTPException: 404 if term not found.

        Example:
            >>> # detail = await ArticlesService.get_admin_term(db, article_id, term_id)
        """
        stmt = (
            select(ArticleSentenceTerm)
            .join(ArticleSentence, ArticleSentenceTerm.sentence_id == ArticleSentence.id)
            .options(selectinload(ArticleSentenceTerm.sentence))
            .where(
                ArticleSentenceTerm.id == term_id,
                ArticleSentence.article_id == article_id,
            )
        )
        res = await db.execute(stmt)
        term = res.scalar_one_or_none()
        if not term:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Term not found")

        parent_s = ArticleSentenceDto.model_validate(term.sentence)
        term_dto = ArticleSentenceTermDto.model_validate(term)
        return AdminArticleTermDetailDto(
            **term_dto.model_dump(),
            parentSentence=parent_s,
        )

    @classmethod
    async def update_admin_term(
        cls,
        db: AsyncSession,
        acting_admin_id: uuid.UUID,
        article_id: uuid.UUID,
        term_id: uuid.UUID,
        dto: UpdateArticleTermDto,
    ) -> ArticleTermMutationDataDto:
        """Updates contextual term metadata and synchronizes HTML markers on value changes.

        Args:
            db (AsyncSession): Active database session.
            acting_admin_id (uuid.UUID): Administrator performing the action.
            article_id (uuid.UUID): Target article identifier.
            term_id (uuid.UUID): Target term identifier.
            dto (UpdateArticleTermDto): Requested term updates.

        Returns:
            ArticleTermMutationDataDto: Updated term and HTML modified indicator.

        Raises:
            HTTPException: 400 if no fields supplied; 404 if term not found; 409 if article archived or unapproved candidate activated directly;
                           422 if new value does not match sentence text.

        Example:
            >>> # res = await ArticlesService.update_admin_term(db, admin_id, art_id, t_id, dto)
        """
        art_res = await db.execute(select(Article).where(Article.id == article_id))
        article = art_res.scalar_one_or_none()
        if not article:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
        if article.status == ArticleStatus.ARCHIVED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Archived articles cannot be modified")

        stmt = (
            select(ArticleSentenceTerm)
            .join(ArticleSentence, ArticleSentenceTerm.sentence_id == ArticleSentence.id)
            .options(selectinload(ArticleSentenceTerm.sentence))
            .where(
                ArticleSentenceTerm.id == term_id,
                ArticleSentence.article_id == article_id,
            )
        )
        res = await db.execute(stmt)
        term = res.scalar_one_or_none()
        if not term:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Term not found")

        # Moderation rule: pending or rejected AI terms cannot be activated or enabled for lookup directly
        if term.review_status != TermReviewStatus.APPROVED and (dto.isActive is True or dto.isLookupEnabled is True):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Pending or rejected AI terms must be approved through the moderation endpoint",
            )

        content_html_changed = False
        if dto.value is not None and dto.value != term.value:
            if not TermMarkerHelper.matches_text(term.sentence.sentence_text, dto.value):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Updated term value does not occur in parent sentence text",
                )
            if term.review_status == TermReviewStatus.APPROVED:
                article.content_html = TermMarkerHelper.replace(article.content_html, term_id, dto.value)
                content_html_changed = True
            term.value = dto.value

        if dto.lemma is not None:
            term.lemma = dto.lemma
        if dto.partOfSpeech is not None:
            term.part_of_speech = dto.partOfSpeech
        if dto.ipa is not None:
            term.ipa = dto.ipa
        if dto.cefrLevel is not None:
            term.cefr_level = dto.cefrLevel
        if dto.contextualMeaningVi is not None:
            term.contextual_meaning_vi = dto.contextualMeaningVi
        if dto.definitionEn is not None:
            term.definition_en = dto.definitionEn
        if dto.contextualExplanation is not None:
            term.contextual_explanation = dto.contextualExplanation
        if dto.synonyms is not None:
            term.synonyms = dto.synonyms
        if dto.antonyms is not None:
            term.antonyms = dto.antonyms
        if dto.collocations is not None:
            term.collocations = dto.collocations
        if dto.relatedTerms is not None:
            term.related_terms = dto.relatedTerms
        if dto.examples is not None:
            term.examples = dto.examples
        if dto.isLookupEnabled is not None:
            term.is_lookup_enabled = dto.isLookupEnabled
        if dto.isActive is not None:
            term.is_active = dto.isActive

        await db.commit()
        await db.refresh(term)

        return ArticleTermMutationDataDto(
            term=ArticleSentenceTermDto.model_validate(term),
            contentHtmlChanged=content_html_changed,
        )

    @classmethod
    async def approve_admin_term(
        cls,
        db: AsyncSession,
        acting_admin_id: uuid.UUID,
        article_id: uuid.UUID,
        term_id: uuid.UUID,
    ) -> ArticleTermMutationDataDto:
        """Approves a pending AI term candidate, activating it and inserting an HTML marker.

        Args:
            db (AsyncSession): Active database session.
            acting_admin_id (uuid.UUID): Administrator performing the action.
            article_id (uuid.UUID): Target article identifier.
            term_id (uuid.UUID): Target term identifier.

        Returns:
            ArticleTermMutationDataDto: Approved term entity and mutation confirmation.

        Raises:
            HTTPException: 404 if term not found; 409 if article not draft, candidate not AI, or candidate already rejected;
                           422 if candidate text no longer matches sentence.

        Example:
            >>> # res = await ArticlesService.approve_admin_term(db, admin_id, article_id, term_id)
        """
        art_res = await db.execute(select(Article).where(Article.id == article_id))
        article = art_res.scalar_one_or_none()
        if not article:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
        if article.status != ArticleStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Moderation is only allowed on draft articles"
            )

        stmt = (
            select(ArticleSentenceTerm)
            .join(ArticleSentence, ArticleSentenceTerm.sentence_id == ArticleSentence.id)
            .options(selectinload(ArticleSentenceTerm.sentence))
            .where(
                ArticleSentenceTerm.id == term_id,
                ArticleSentence.article_id == article_id,
            )
        )
        res = await db.execute(stmt)
        term = res.scalar_one_or_none()
        if not term:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Term not found")
        if term.origin != TermOrigin.AI:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only AI term candidates can be approved")
        if not term.sentence.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Terms cannot be approved in an inactive sentence"
            )

        # Idempotent return if already approved
        if term.review_status == TermReviewStatus.APPROVED:
            return ArticleTermMutationDataDto(
                term=ArticleSentenceTermDto.model_validate(term),
                contentHtmlChanged=False,
            )
        if term.review_status == TermReviewStatus.REJECTED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Rejected AI term candidates cannot be approved"
            )

        if not TermMarkerHelper.matches_text(term.sentence.sentence_text, term.value):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Term candidate value no longer matches sentence text",
            )

        updated_html = TermMarkerHelper.insert_first(article.content_html, term.sentence.id, term.id, term.value)
        content_changed = updated_html != article.content_html
        if content_changed:
            article.content_html = updated_html

        term.review_status = TermReviewStatus.APPROVED
        term.is_active = True
        term.is_lookup_enabled = True

        await db.commit()
        await db.refresh(term)

        return ArticleTermMutationDataDto(
            term=ArticleSentenceTermDto.model_validate(term),
            contentHtmlChanged=content_changed,
        )

    @classmethod
    async def reject_admin_term(
        cls,
        db: AsyncSession,
        acting_admin_id: uuid.UUID,
        article_id: uuid.UUID,
        term_id: uuid.UUID,
    ) -> ArticleTermMutationDataDto:
        """Rejects a pending AI term candidate without inserting HTML markers.

        Args:
            db (AsyncSession): Active database session.
            acting_admin_id (uuid.UUID): Administrator performing the action.
            article_id (uuid.UUID): Target article identifier.
            term_id (uuid.UUID): Target term identifier.

        Returns:
            ArticleTermMutationDataDto: Rejected term entity.

        Raises:
            HTTPException: 404 if term not found; 409 if article not draft, candidate not AI, or candidate already approved.

        Example:
            >>> # res = await ArticlesService.reject_admin_term(db, admin_id, article_id, term_id)
        """
        art_res = await db.execute(select(Article).where(Article.id == article_id))
        article = art_res.scalar_one_or_none()
        if not article:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
        if article.status != ArticleStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Moderation is only allowed on draft articles"
            )

        stmt = (
            select(ArticleSentenceTerm)
            .join(ArticleSentence, ArticleSentenceTerm.sentence_id == ArticleSentence.id)
            .where(
                ArticleSentenceTerm.id == term_id,
                ArticleSentence.article_id == article_id,
            )
        )
        res = await db.execute(stmt)
        term = res.scalar_one_or_none()
        if not term:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Term not found")
        if term.origin != TermOrigin.AI:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only AI term candidates can be rejected")

        # Idempotent return if already rejected
        if term.review_status == TermReviewStatus.REJECTED:
            return ArticleTermMutationDataDto(
                term=ArticleSentenceTermDto.model_validate(term),
                contentHtmlChanged=False,
            )
        if term.review_status == TermReviewStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Approved AI term candidates cannot be rejected"
            )

        term.review_status = TermReviewStatus.REJECTED
        term.is_active = False
        term.is_lookup_enabled = False

        await db.commit()
        await db.refresh(term)

        return ArticleTermMutationDataDto(
            term=ArticleSentenceTermDto.model_validate(term),
            contentHtmlChanged=False,
        )

    @classmethod
    async def delete_admin_term(
        cls,
        db: AsyncSession,
        acting_admin_id: uuid.UUID,
        article_id: uuid.UUID,
        term_id: uuid.UUID,
    ) -> None:
        """Deletes an unreferenced contextual term and removes its HTML marker span.

        Args:
            db (AsyncSession): Active database session.
            acting_admin_id (uuid.UUID): Administrator performing the action.
            article_id (uuid.UUID): Target article identifier.
            term_id (uuid.UUID): Target term identifier.

        Raises:
            HTTPException: 404 if term not found; 409 if article is archived or term is referenced in saved vocabulary.

        Example:
            >>> # await ArticlesService.delete_admin_term(db, admin_id, article_id, term_id)
        """
        art_res = await db.execute(select(Article).where(Article.id == article_id))
        article = art_res.scalar_one_or_none()
        if not article:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
        if article.status == ArticleStatus.ARCHIVED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Archived articles cannot be modified")

        stmt = (
            select(ArticleSentenceTerm)
            .join(ArticleSentence, ArticleSentenceTerm.sentence_id == ArticleSentence.id)
            .where(
                ArticleSentenceTerm.id == term_id,
                ArticleSentence.article_id == article_id,
            )
        )
        res = await db.execute(stmt)
        term = res.scalar_one_or_none()
        if not term:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Term not found")

        # Check referential integrity: reject if saved vocabulary references this term
        v_count_res = await db.execute(
            select(func.count()).select_from(UserVocabulary).where(UserVocabulary.article_sentence_term_id == term_id)
        )
        if v_count_res.scalar_one() > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Term is referenced in saved vocabulary and cannot be deleted",
            )

        # Unwrap HTML marker
        article.content_html = TermMarkerHelper.unwrap(article.content_html, term_id)
        await db.delete(term)
        await db.commit()

    @classmethod
    async def find_imported_duplicate(cls, db: AsyncSession, external_id: str) -> bool:
        """Checks if an article with the externalId has already been imported.

        Args:
            db (AsyncSession): Active database session.
            external_id (str): Source system external identifier.

        Returns:
            bool: True if article with external ID already exists, False otherwise.

        Example:
            >>> # exists = await ArticlesService.find_imported_duplicate(db, "ext-123")
        """
        res = await db.execute(select(Article.id).where(Article.external_id == external_id))
        return res.scalar_one_or_none() is not None

    @classmethod
    async def create_imported_draft(
        cls,
        db: AsyncSession,
        acting_admin_id: uuid.UUID,
        data: dict,
    ) -> Article:
        """Creates a local draft article for an imported news item.

        Args:
            db (AsyncSession): Active database session.
            acting_admin_id (uuid.UUID): Administrator or system actor importing the article.
            data (dict): Dictionary payload with article fields.

        Returns:
            Article: Newly created draft Article entity.

        Raises:
            HTTPException: 409 if external ID or slug already exists.

        Example:
            >>> # article = await ArticlesService.create_imported_draft(db, admin_id, item_data)
        """
        if await cls.find_imported_duplicate(db, data["externalId"]):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Imported article already exists",
            )

        sanitized_html = HtmlSanitizerHelper.sanitize(data["contentHtml"])
        article = Article(
            id=uuid.uuid4(),
            category_id=data["categoryId"],
            title=data["title"],
            slug=data["slug"],
            summary=data.get("summary"),
            content_html=sanitized_html,
            status=ArticleStatus.DRAFT,
            cefr_level=CefrLevel.B1,
            ai_analysis_status=AiGenerationStatus.PENDING,
            source_name=data.get("sourceName", "The Guardian"),
            source_url=data.get("sourceUrl"),
            external_id=data.get("externalId"),
            source_published_at=data.get("sourcePublishedAt"),
            thumbnail_url=data.get("thumbnailUrl"),
            author_name=data.get("authorName"),
            content_version=1,
        )
        db.add(article)
        try:
            await db.commit()
            await db.refresh(article)
            return article
        except IntegrityError as err:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Article slug or external ID already exists",
            ) from err
