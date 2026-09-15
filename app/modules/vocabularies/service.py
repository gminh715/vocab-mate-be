"""Service layer for the Vocabularies module."""

import json
import math
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.articles import Article, ArticleSentence, ArticleSentenceTerm
from app.models.collections import VocabularyCollection, VocabularyCollectionItem
from app.models.enums import ArticleStatus, CefrLevel
from app.models.vocabularies import UserVocabulary
from app.modules.vocabularies.schemas import (
    GetVocabulariesQueryDto,
    PaginationMetaDto,
    SaveVocabularyDto,
    VocabularyCollectionSummaryDto,
    VocabularyDetailDataDto,
    VocabularyDetailDto,
    VocabularyListDataDto,
    VocabularyListItemDto,
    VocabularySaveDataDto,
    VocabularySourceArticleDto,
)


class VocabulariesService:
    """Service managing user saved vocabulary items and snapshots."""

    @classmethod
    async def find_all(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        query: GetVocabulariesQueryDto,
    ) -> VocabularyListDataDto:
        """Retrieves a paginated and filtered list of user saved vocabulary snapshots.

        Args:
            db (AsyncSession): Active asynchronous database session.
            user_id (uuid.UUID): Authenticated owner user unique identifier.
            query (GetVocabulariesQueryDto): Filtering and pagination query parameters.

        Returns:
            VocabularyListDataDto: Data transfer object containing vocabulary items and pagination meta.

        Example:
            >>> # result = await VocabulariesService.find_all(db, user_id, query)
        """
        stmt = (
            select(UserVocabulary)
            .options(selectinload(UserVocabulary.collection_items).selectinload(VocabularyCollectionItem.collection))
            .where(UserVocabulary.user_id == user_id)
        )
        if query.cefrLevel:
            stmt = stmt.where(UserVocabulary.saved_cefr_level == query.cefrLevel)
        if query.collectionId:
            stmt = stmt.join(
                VocabularyCollectionItem,
                UserVocabulary.id == VocabularyCollectionItem.user_vocabulary_id,
            ).where(VocabularyCollectionItem.collection_id == query.collectionId)
        if query.q and query.q.strip():
            q_val = f"%{query.q.strip()}%"
            stmt = stmt.where(
                or_(
                    UserVocabulary.saved_word_display.ilike(q_val),
                    UserVocabulary.saved_lemma.ilike(q_val),
                    UserVocabulary.saved_meaning_vi.ilike(q_val),
                )
            )

        # Count total
        count_stmt = select(func.count()).select_from(UserVocabulary).where(UserVocabulary.user_id == user_id)
        if query.cefrLevel:
            count_stmt = count_stmt.where(UserVocabulary.saved_cefr_level == query.cefrLevel)
        if query.collectionId:
            count_stmt = count_stmt.join(
                VocabularyCollectionItem,
                UserVocabulary.id == VocabularyCollectionItem.user_vocabulary_id,
            ).where(VocabularyCollectionItem.collection_id == query.collectionId)
        if query.q and query.q.strip():
            q_val = f"%{query.q.strip()}%"
            count_stmt = count_stmt.where(
                or_(
                    UserVocabulary.saved_word_display.ilike(q_val),
                    UserVocabulary.saved_lemma.ilike(q_val),
                    UserVocabulary.saved_meaning_vi.ilike(q_val),
                )
            )
        total = (await db.execute(count_stmt)).scalar_one()

        order_col = UserVocabulary.saved_at.asc() if query.sort == "oldest" else UserVocabulary.saved_at.desc()
        stmt = (
            stmt.order_by(order_col, UserVocabulary.id.asc()).offset((query.page - 1) * query.limit).limit(query.limit)
        )

        res = await db.execute(stmt)
        rows = res.scalars().all()

        items = []
        for uv in rows:
            cols = [
                VocabularyCollectionSummaryDto(
                    id=ci.collection.id,
                    name=ci.collection.name,
                    addedAt=ci.added_at,
                )
                for ci in uv.collection_items
                if ci.collection
            ]
            items.append(
                VocabularyListItemDto(
                    id=uv.id,
                    articleSentenceTermId=uv.article_sentence_term_id,
                    savedWordDisplay=uv.saved_word_display,
                    savedLemma=uv.saved_lemma,
                    savedPartOfSpeech=uv.saved_part_of_speech,
                    savedIpa=uv.saved_ipa,
                    savedCefrLevel=uv.saved_cefr_level,
                    savedMeaningVi=uv.saved_meaning_vi,
                    definitionEn=uv.definition_en,
                    savedAt=uv.saved_at,
                    createdAt=uv.created_at,
                    collections=cols,
                )
            )

        return VocabularyListDataDto(
            items=items,
            meta=PaginationMetaDto(
                page=query.page,
                limit=query.limit,
                total=total,
                totalPages=math.ceil(total / query.limit) if query.limit > 0 else 0,
            ),
        )

    @classmethod
    async def find_one(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        user_vocabulary_id: uuid.UUID,
    ) -> VocabularyDetailDataDto:
        """Retrieves a single saved vocabulary snapshot with associated collections and article context.

        Args:
            db (AsyncSession): Active asynchronous database session.
            user_id (uuid.UUID): Authenticated owner user unique identifier.
            user_vocabulary_id (uuid.UUID): Target saved vocabulary item UUID.

        Returns:
            VocabularyDetailDataDto: Detail payload including term attributes, collections, and source article.

        Raises:
            HTTPException: 404 Not Found if the saved vocabulary item does not exist or belongs to another user.

        Example:
            >>> # result = await VocabulariesService.find_one(db, user_id, vocab_id)
        """
        stmt = (
            select(UserVocabulary)
            .options(
                selectinload(UserVocabulary.collection_items).selectinload(VocabularyCollectionItem.collection),
                selectinload(UserVocabulary.article_sentence_term)
                .selectinload(ArticleSentenceTerm.sentence)
                .selectinload(ArticleSentence.article),
            )
            .where(
                UserVocabulary.id == user_vocabulary_id,
                UserVocabulary.user_id == user_id,
            )
        )
        res = await db.execute(stmt)
        uv = res.scalar_one_or_none()
        if not uv:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved vocabulary not found")

        cols = [
            VocabularyCollectionSummaryDto(
                id=ci.collection.id,
                name=ci.collection.name,
                addedAt=ci.added_at,
            )
            for ci in uv.collection_items
            if ci.collection
        ]

        article = (
            uv.article_sentence_term.sentence.article
            if uv.article_sentence_term and uv.article_sentence_term.sentence
            else None
        )
        source_article = (
            VocabularySourceArticleDto(
                id=article.id,
                slug=article.slug,
                title=article.title,
                thumbnailUrl=article.thumbnail_url,
                sourceName=article.source_name,
                sourceUrl=article.source_url,
            )
            if article
            else VocabularySourceArticleDto(
                id=uuid.uuid4(),
                slug="",
                title="",
                thumbnailUrl=None,
                sourceName=None,
                sourceUrl=None,
            )
        )

        examples = uv.saved_examples if isinstance(uv.saved_examples, list) else []

        vocab_detail = VocabularyDetailDto(
            id=uv.id,
            articleSentenceTermId=uv.article_sentence_term_id,
            savedWordDisplay=uv.saved_word_display,
            savedLemma=uv.saved_lemma,
            savedPartOfSpeech=uv.saved_part_of_speech,
            savedIpa=uv.saved_ipa,
            savedCefrLevel=uv.saved_cefr_level,
            savedMeaningVi=uv.saved_meaning_vi,
            definitionEn=uv.definition_en,
            savedAt=uv.saved_at,
            createdAt=uv.created_at,
            savedExamples=examples,
        )

        return VocabularyDetailDataDto(
            vocabulary=vocab_detail,
            collections=cols,
            sourceArticle=source_article,
        )

    @classmethod
    async def save(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        dto: SaveVocabularyDto,
    ) -> VocabularySaveDataDto:
        """Captures an eligible contextual term occurrence as an immutable personal vocabulary snapshot.

        Args:
            db (AsyncSession): Active asynchronous database session.
            user_id (uuid.UUID): Authenticated learner user unique identifier.
            dto (SaveVocabularyDto): Target term reference and initial collection IDs.

        Returns:
            VocabularySaveDataDto: Saved vocabulary item details and associated collections summary.

        Raises:
            HTTPException: 400 Bad Request if no collections provided.
            HTTPException: 422 Unprocessable Entity if specified collections are missing or not owned.
            HTTPException: 409 Conflict if this user already saved this contextual term.
            HTTPException: 404 Not Found if term is missing, inactive, or article is not published.
            HTTPException: 403 Forbidden if term lookup is disabled.

        Example:
            >>> # result = await VocabulariesService.save(db, user_id, dto)
        """
        if not dto.collectionIds:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one collection is required to save vocabulary",
            )

        unique_col_ids = list(set(dto.collectionIds))
        cols_res = await db.execute(
            select(VocabularyCollection).where(
                VocabularyCollection.user_id == user_id,
                VocabularyCollection.id.in_(unique_col_ids),
            )
        )
        cols = cols_res.scalars().all()
        if len(cols) != len(unique_col_ids):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="At least one requested collection was not found or is not owned by the caller",
            )

        # Check duplicate
        existing = await db.scalar(
            select(UserVocabulary).where(
                UserVocabulary.user_id == user_id,
                UserVocabulary.article_sentence_term_id == dto.articleSentenceTermId,
            )
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The contextual term has already been saved by this user",
            )

        # Verify source term
        term_stmt = (
            select(ArticleSentenceTerm)
            .join(ArticleSentence, ArticleSentenceTerm.sentence_id == ArticleSentence.id)
            .join(Article, ArticleSentence.article_id == Article.id)
            .where(
                ArticleSentenceTerm.id == dto.articleSentenceTermId,
                Article.status == ArticleStatus.PUBLISHED,
                ArticleSentence.content_version == Article.content_version,
                ArticleSentence.is_active.is_(True),
                ArticleSentenceTerm.is_active.is_(True),
            )
        )
        term = await db.scalar(term_stmt)
        if not term:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The term is missing, inactive, stale, or not in a published article",
            )
        if not term.is_lookup_enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Contextual lookup is disabled for this term",
            )

        now = datetime.now(UTC)
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

        meaning_vi = (term.contextual_meaning_vi or "").strip()
        if not meaning_vi:
            meaning_vi = term.value.strip()

        definition_en = (term.definition_en or "").strip() or None

        uv = UserVocabulary(
            id=uuid.uuid4(),
            user_id=user_id,
            article_sentence_term_id=term.id,
            saved_word_display=term.value.strip(),
            saved_lemma=(term.lemma or term.value).strip(),
            saved_part_of_speech=(term.part_of_speech or "word").strip(),
            saved_ipa=term.ipa.strip() if term.ipa else None,
            saved_cefr_level=term.cefr_level or CefrLevel.B1,
            saved_meaning_vi=meaning_vi,
            definition_en=definition_en,
            saved_examples=examples if isinstance(examples, list) else [],
            saved_at=now,
            created_at=now,
        )
        db.add(uv)
        await db.flush()

        col_summaries = []
        for col in cols:
            db.add(
                VocabularyCollectionItem(
                    collection_id=col.id,
                    user_vocabulary_id=uv.id,
                    added_at=now,
                )
            )
            col_summaries.append(VocabularyCollectionSummaryDto(id=col.id, name=col.name, addedAt=now))

        await db.commit()

        vocab_detail = VocabularyDetailDto(
            id=uv.id,
            articleSentenceTermId=uv.article_sentence_term_id,
            savedWordDisplay=uv.saved_word_display,
            savedLemma=uv.saved_lemma,
            savedPartOfSpeech=uv.saved_part_of_speech,
            savedIpa=uv.saved_ipa,
            savedCefrLevel=uv.saved_cefr_level,
            savedMeaningVi=uv.saved_meaning_vi,
            definitionEn=uv.definition_en,
            savedAt=uv.saved_at,
            createdAt=uv.created_at,
            savedExamples=examples,
        )

        return VocabularySaveDataDto(vocabulary=vocab_detail, collections=col_summaries)

    @classmethod
    async def remove(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        user_vocabulary_id: uuid.UUID,
    ) -> None:
        """Deletes a saved vocabulary snapshot belonging to the authenticated user.

        Args:
            db (AsyncSession): Active asynchronous database session.
            user_id (uuid.UUID): Authenticated owner user unique identifier.
            user_vocabulary_id (uuid.UUID): Saved vocabulary unique identifier.

        Returns:
            None: Deletion succeeds without return payload.

        Raises:
            HTTPException: 404 Not Found if the vocabulary item was not found or is not owned by user.

        Example:
            >>> # await VocabulariesService.remove(db, user_id, vocab_id)
        """
        res = await db.execute(
            delete(UserVocabulary).where(
                UserVocabulary.id == user_vocabulary_id,
                UserVocabulary.user_id == user_id,
            )
        )
        await db.commit()
        if res.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved vocabulary not found")
