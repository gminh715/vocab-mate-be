"""Service layer for the Collections module."""

import math
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collections import VocabularyCollection, VocabularyCollectionItem
from app.models.vocabularies import UserVocabulary
from app.modules.collections.schemas import (
    AddCollectionItemsDto,
    CollectionDetailDataDto,
    CollectionDto,
    CollectionItemsAddDataDto,
    CollectionItemsListDataDto,
    CollectionListDataDto,
    CollectionListItemDto,
    CollectionMutationDataDto,
    CollectionVocabularyItemDto,
    CreateCollectionDto,
    GetCollectionItemsQueryDto,
    GetCollectionsQueryDto,
    PaginationMetaDto,
    UpdateCollectionDto,
)


class CollectionsService:
    """Service managing user vocabulary collections and item memberships."""

    @classmethod
    async def find_all(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        query: GetCollectionsQueryDto,
    ) -> CollectionListDataDto:
        """Retrieves paginated collections owned by the authenticated caller.

        Args:
            db (AsyncSession): Active asynchronous database session.
            user_id (uuid.UUID): Authenticated owner user unique identifier.
            query (GetCollectionsQueryDto): Search and pagination query parameters.

        Returns:
            CollectionListDataDto: List of user collections with item counts and pagination metadata.

        Example:
            >>> # result = await CollectionsService.find_all(db, user_id, query)
        """
        stmt = (
            select(
                VocabularyCollection,
                func.count(VocabularyCollectionItem.user_vocabulary_id).label("vocab_count"),
            )
            .outerjoin(
                VocabularyCollectionItem,
                VocabularyCollection.id == VocabularyCollectionItem.collection_id,
            )
            .where(VocabularyCollection.user_id == user_id)
            .group_by(VocabularyCollection.id)
        )
        if query.q and query.q.strip():
            stmt = stmt.where(VocabularyCollection.name.ilike(f"%{query.q.strip()}%"))

        count_stmt = (
            select(func.count()).select_from(VocabularyCollection).where(VocabularyCollection.user_id == user_id)
        )
        if query.q and query.q.strip():
            count_stmt = count_stmt.where(VocabularyCollection.name.ilike(f"%{query.q.strip()}%"))

        total = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            stmt.order_by(VocabularyCollection.created_at.desc(), VocabularyCollection.id.asc())
            .offset((query.page - 1) * query.limit)
            .limit(query.limit)
        )
        res = await db.execute(stmt)
        rows = res.all()

        items = [
            CollectionListItemDto(
                id=col.id,
                name=col.name,
                createdAt=col.created_at,
                updatedAt=col.updated_at,
                vocabularyCount=v_count,
            )
            for col, v_count in rows
        ]

        return CollectionListDataDto(
            items=items,
            meta=PaginationMetaDto(
                page=query.page,
                limit=query.limit,
                total=total,
                totalPages=math.ceil(total / query.limit) if query.limit > 0 else 0,
            ),
        )

    @classmethod
    async def create(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        dto: CreateCollectionDto,
    ) -> CollectionMutationDataDto:
        """Creates a new collection owned by the authenticated caller.

        Args:
            db (AsyncSession): Active asynchronous database session.
            user_id (uuid.UUID): Authenticated owner user unique identifier.
            dto (CreateCollectionDto): Collection creation payload with unique name.

        Returns:
            CollectionMutationDataDto: Created collection entity wrapper.

        Raises:
            HTTPException: 409 Conflict if caller already owns a collection with this name.

        Example:
            >>> # result = await CollectionsService.create(db, user_id, dto)
        """
        name = dto.name.strip()
        existing = await db.scalar(
            select(VocabularyCollection).where(
                VocabularyCollection.user_id == user_id,
                VocabularyCollection.name == name,
            )
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The user already has a collection with this exact name.",
            )

        col = VocabularyCollection(id=uuid.uuid4(), user_id=user_id, name=name)
        db.add(col)
        await db.commit()
        await db.refresh(col)

        return CollectionMutationDataDto(
            collection=CollectionDto(
                id=col.id,
                name=col.name,
                createdAt=col.created_at,
                updatedAt=col.updated_at,
            )
        )

    @classmethod
    async def find_one(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        collection_id: uuid.UUID,
    ) -> CollectionDetailDataDto:
        """Retrieves an owner-scoped collection and its total vocabulary count.

        Args:
            db (AsyncSession): Active asynchronous database session.
            user_id (uuid.UUID): Authenticated owner user unique identifier.
            collection_id (uuid.UUID): Target collection UUID.

        Returns:
            CollectionDetailDataDto: Detailed collection payload with total vocabulary count.

        Raises:
            HTTPException: 404 Not Found if collection does not exist or belongs to another user.

        Example:
            >>> # result = await CollectionsService.find_one(db, user_id, col_id)
        """
        stmt = (
            select(
                VocabularyCollection,
                func.count(VocabularyCollectionItem.user_vocabulary_id).label("vocab_count"),
            )
            .outerjoin(
                VocabularyCollectionItem,
                VocabularyCollection.id == VocabularyCollectionItem.collection_id,
            )
            .where(
                VocabularyCollection.id == collection_id,
                VocabularyCollection.user_id == user_id,
            )
            .group_by(VocabularyCollection.id)
        )
        res = await db.execute(stmt)
        row = res.first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")

        col, v_count = row
        return CollectionDetailDataDto(
            collection=CollectionDto(
                id=col.id,
                name=col.name,
                createdAt=col.created_at,
                updatedAt=col.updated_at,
            ),
            vocabularyCount=v_count,
        )

    @classmethod
    async def update(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        collection_id: uuid.UUID,
        dto: UpdateCollectionDto,
    ) -> CollectionMutationDataDto:
        """Partially updates an owned collection's name.

        Args:
            db (AsyncSession): Active asynchronous database session.
            user_id (uuid.UUID): Authenticated owner user unique identifier.
            collection_id (uuid.UUID): Target collection UUID.
            dto (UpdateCollectionDto): Updated collection name payload.

        Returns:
            CollectionMutationDataDto: Updated collection entity wrapper.

        Raises:
            HTTPException: 404 Not Found if collection is missing or unowned.
            HTTPException: 409 Conflict if another owned collection shares this name.

        Example:
            >>> # result = await CollectionsService.update(db, user_id, col_id, dto)
        """
        col = await db.scalar(
            select(VocabularyCollection).where(
                VocabularyCollection.id == collection_id,
                VocabularyCollection.user_id == user_id,
            )
        )
        if not col:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")

        name = dto.name.strip()
        collision = await db.scalar(
            select(VocabularyCollection).where(
                VocabularyCollection.user_id == user_id,
                VocabularyCollection.name == name,
                VocabularyCollection.id != collection_id,
            )
        )
        if collision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The user already has a collection with this exact name.",
            )

        col.name = name
        await db.commit()
        await db.refresh(col)

        return CollectionMutationDataDto(
            collection=CollectionDto(
                id=col.id,
                name=col.name,
                createdAt=col.created_at,
                updatedAt=col.updated_at,
            )
        )

    @classmethod
    async def delete(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        collection_id: uuid.UUID,
    ) -> None:
        """Deletes an owned collection and cleans up vocabulary items belonging exclusively to it.

        Args:
            db (AsyncSession): Active asynchronous database session.
            user_id (uuid.UUID): Authenticated owner user unique identifier.
            collection_id (uuid.UUID): Target collection UUID to delete.

        Returns:
            None: Deletion completes without return payload.

        Raises:
            HTTPException: 404 Not Found if collection does not exist or is unowned.

        Example:
            >>> # await CollectionsService.delete(db, user_id, col_id)
        """
        col = await db.scalar(
            select(VocabularyCollection).where(
                VocabularyCollection.id == collection_id,
                VocabularyCollection.user_id == user_id,
            )
        )
        if not col:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")

        # Find user vocabularies belonging solely to this collection
        in_target = select(VocabularyCollectionItem.user_vocabulary_id).where(
            VocabularyCollectionItem.collection_id == collection_id
        )
        in_others = select(VocabularyCollectionItem.user_vocabulary_id).where(
            VocabularyCollectionItem.collection_id != collection_id
        )
        exclusive_uv_ids_stmt = select(UserVocabulary.id).where(
            UserVocabulary.user_id == user_id,
            UserVocabulary.id.in_(in_target),
            ~UserVocabulary.id.in_(in_others),
        )
        exclusive_uv_ids = (await db.execute(exclusive_uv_ids_stmt)).scalars().all()
        if exclusive_uv_ids:
            await db.execute(delete(UserVocabulary).where(UserVocabulary.id.in_(exclusive_uv_ids)))

        await db.delete(col)
        await db.commit()

    @classmethod
    async def find_items(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        collection_id: uuid.UUID,
        query: GetCollectionItemsQueryDto,
    ) -> CollectionItemsListDataDto:
        """Retrieves paginated vocabulary snapshot items within an owned collection.

        Args:
            db (AsyncSession): Active asynchronous database session.
            user_id (uuid.UUID): Authenticated owner user unique identifier.
            collection_id (uuid.UUID): Target collection UUID.
            query (GetCollectionItemsQueryDto): Filter and pagination query parameters.

        Returns:
            CollectionItemsListDataDto: Paginated list of collection items with metadata.

        Raises:
            HTTPException: 404 Not Found if collection does not exist or is unowned.

        Example:
            >>> # result = await CollectionsService.find_items(db, user_id, col_id, query)
        """
        col = await db.scalar(
            select(VocabularyCollection).where(
                VocabularyCollection.id == collection_id,
                VocabularyCollection.user_id == user_id,
            )
        )
        if not col:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")

        stmt = (
            select(UserVocabulary, VocabularyCollectionItem.added_at)
            .join(
                VocabularyCollectionItem,
                UserVocabulary.id == VocabularyCollectionItem.user_vocabulary_id,
            )
            .where(
                VocabularyCollectionItem.collection_id == collection_id,
                UserVocabulary.user_id == user_id,
            )
        )
        if query.q and query.q.strip():
            q_val = f"%{query.q.strip()}%"
            stmt = stmt.where(
                or_(
                    UserVocabulary.saved_word_display.ilike(q_val),
                    UserVocabulary.saved_lemma.ilike(q_val),
                    UserVocabulary.saved_meaning_vi.ilike(q_val),
                )
            )

        count_stmt = (
            select(func.count())
            .select_from(VocabularyCollectionItem)
            .join(
                UserVocabulary,
                VocabularyCollectionItem.user_vocabulary_id == UserVocabulary.id,
            )
            .where(
                VocabularyCollectionItem.collection_id == collection_id,
                UserVocabulary.user_id == user_id,
            )
        )
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

        order_col = (
            VocabularyCollectionItem.added_at.asc()
            if query.sort == "oldest"
            else VocabularyCollectionItem.added_at.desc()
        )
        stmt = (
            stmt.order_by(order_col, UserVocabulary.id.asc()).offset((query.page - 1) * query.limit).limit(query.limit)
        )

        res = await db.execute(stmt)
        rows = res.all()

        items = [
            CollectionVocabularyItemDto(
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
                addedAt=added_at,
            )
            for uv, added_at in rows
        ]

        return CollectionItemsListDataDto(
            items=items,
            meta=PaginationMetaDto(
                page=query.page,
                limit=query.limit,
                total=total,
                totalPages=math.ceil(total / query.limit) if query.limit > 0 else 0,
            ),
        )

    @classmethod
    async def add_items(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        collection_id: uuid.UUID,
        dto: AddCollectionItemsDto,
    ) -> CollectionItemsAddDataDto:
        """Bulk associates saved vocabulary items to an owned collection.

        Args:
            db (AsyncSession): Active asynchronous database session.
            user_id (uuid.UUID): Authenticated owner user unique identifier.
            collection_id (uuid.UUID): Target collection UUID.
            dto (AddCollectionItemsDto): List of user vocabulary item UUIDs to add.

        Returns:
            CollectionItemsAddDataDto: Added and skipped counts summary.

        Raises:
            HTTPException: 404 Not Found if collection is missing or unowned.
            HTTPException: 422 Unprocessable Entity if any vocabulary item is unowned or missing.

        Example:
            >>> # result = await CollectionsService.add_items(db, user_id, col_id, dto)
        """
        col = await db.scalar(
            select(VocabularyCollection).where(
                VocabularyCollection.id == collection_id,
                VocabularyCollection.user_id == user_id,
            )
        )
        if not col:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")

        unique_ids = list(set(dto.userVocabularyIds))
        owned_res = await db.execute(
            select(UserVocabulary.id).where(
                UserVocabulary.user_id == user_id,
                UserVocabulary.id.in_(unique_ids),
            )
        )
        owned_ids = set(owned_res.scalars().all())
        if len(owned_ids) != len(unique_ids):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="At least one requested saved vocabulary is missing or not owned by the caller.",
            )

        existing_res = await db.execute(
            select(VocabularyCollectionItem.user_vocabulary_id).where(
                VocabularyCollectionItem.collection_id == collection_id,
                VocabularyCollectionItem.user_vocabulary_id.in_(unique_ids),
            )
        )
        existing_in_col = set(existing_res.scalars().all())
        to_add = [uv_id for uv_id in unique_ids if uv_id not in existing_in_col]

        now = datetime.now(UTC)
        for uv_id in to_add:
            db.add(
                VocabularyCollectionItem(
                    collection_id=collection_id,
                    user_vocabulary_id=uv_id,
                    added_at=now,
                )
            )

        await db.commit()
        added_count = len(to_add)
        skipped_count = len(dto.userVocabularyIds) - added_count

        return CollectionItemsAddDataDto(addedCount=added_count, skippedCount=skipped_count)

    @classmethod
    async def delete_item(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        collection_id: uuid.UUID,
        user_vocabulary_id: uuid.UUID,
    ) -> None:
        """Removes a single saved vocabulary relation from an owned collection.

        Args:
            db (AsyncSession): Active asynchronous database session.
            user_id (uuid.UUID): Authenticated owner user unique identifier.
            collection_id (uuid.UUID): Target collection UUID.
            user_vocabulary_id (uuid.UUID): User vocabulary item UUID to un-link.

        Returns:
            None: Removal completes without return payload.

        Raises:
            HTTPException: 404 Not Found if collection or relationship does not exist.

        Example:
            >>> # await CollectionsService.delete_item(db, user_id, col_id, uv_id)
        """
        col = await db.scalar(
            select(VocabularyCollection).where(
                VocabularyCollection.id == collection_id,
                VocabularyCollection.user_id == user_id,
            )
        )
        if not col:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")

        res = await db.execute(
            delete(VocabularyCollectionItem).where(
                VocabularyCollectionItem.collection_id == collection_id,
                VocabularyCollectionItem.user_vocabulary_id == user_vocabulary_id,
            )
        )
        await db.commit()
        if res.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The collection, vocabulary, or matching owner-scoped relation was not found.",
            )
