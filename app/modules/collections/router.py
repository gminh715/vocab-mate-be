"""FastAPI router for the Collections module managing vocabulary folders."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response, status

from app.common.deps import CurrentUserDep, DbSessionDep
from app.common.response import BaseResponse
from app.modules.collections.schemas import (
    AddCollectionItemsDto,
    CollectionDetailDataDto,
    CollectionItemsAddDataDto,
    CollectionItemsListDataDto,
    CollectionListDataDto,
    CollectionMutationDataDto,
    CreateCollectionDto,
    GetCollectionItemsQueryDto,
    GetCollectionsQueryDto,
    UpdateCollectionDto,
)
from app.modules.collections.service import CollectionsService

router = APIRouter(prefix="/api/v1/collections", tags=["Collections"])


@router.get("", summary="List the authenticated user collections")
async def get_collections(
    db: DbSessionDep,
    user: CurrentUserDep,
    query: Annotated[GetCollectionsQueryDto, Depends()],
) -> BaseResponse[CollectionListDataDto]:
    """Retrieves paginated collections owned by the caller.

    Args:
        db (AsyncSession): Active database session dependency.
        user (User): Authenticated user dependency.
        query (GetCollectionsQueryDto): Search and pagination parameters.

    Returns:
        BaseResponse[CollectionListDataDto]: Envelope enclosing collections and pagination metadata.

    Example:
        >>> # GET /api/v1/collections?page=1&limit=20&q=Tech
    """
    data = await CollectionsService.find_all(db, user.id, query)
    return BaseResponse(success=True, data=data)


@router.post("", summary="Create a collection for the authenticated user", status_code=status.HTTP_201_CREATED)
async def create_collection(
    db: DbSessionDep,
    user: CurrentUserDep,
    dto: CreateCollectionDto,
) -> BaseResponse[CollectionMutationDataDto]:
    """Creates a new collection owned by the authenticated caller.

    Args:
        db (AsyncSession): Active database session dependency.
        user (User): Authenticated user dependency.
        dto (CreateCollectionDto): New collection attributes payload.

    Returns:
        BaseResponse[CollectionMutationDataDto]: Envelope enclosing the newly created collection.

    Raises:
        AppException: 409 Conflict if user already has a collection with this name.

    Example:
        >>> # POST /api/v1/collections with {"name": "AI Vocabulary"}
    """
    data = await CollectionsService.create(db, user.id, dto)
    return BaseResponse(success=True, data=data)


@router.get("/{collection_id}", summary="Get an owner-scoped collection by ID")
async def get_collection(
    db: DbSessionDep,
    user: CurrentUserDep,
    collection_id: Annotated[uuid.UUID, Path(description="Target collection unique identifier")],
) -> BaseResponse[CollectionDetailDataDto]:
    """Retrieves an owned collection and its total vocabulary count.

    Args:
        db (AsyncSession): Active database session dependency.
        user (User): Authenticated user dependency.
        collection_id (uuid.UUID): Target collection unique identifier.

    Returns:
        BaseResponse[CollectionDetailDataDto]: Envelope enclosing collection details and item count.

    Raises:
        AppException: 404 Not Found if collection is missing or not owned by user.

    Example:
        >>> # GET /api/v1/collections/11111111-2222-3333-4444-555555555555
    """
    data = await CollectionsService.find_one(db, user.id, collection_id)
    return BaseResponse(success=True, data=data)


@router.patch("/{collection_id}", summary="Partially update an owner-scoped collection")
async def update_collection(
    db: DbSessionDep,
    user: CurrentUserDep,
    collection_id: Annotated[uuid.UUID, Path(description="Target collection unique identifier")],
    dto: UpdateCollectionDto,
) -> BaseResponse[CollectionMutationDataDto]:
    """Updates an owned collection's name.

    Args:
        db (AsyncSession): Active database session dependency.
        user (User): Authenticated user dependency.
        collection_id (uuid.UUID): Target collection unique identifier.
        dto (UpdateCollectionDto): Updated collection attributes payload.

    Returns:
        BaseResponse[CollectionMutationDataDto]: Envelope enclosing updated collection.

    Raises:
        AppException: 404 Not Found if missing or unowned; 409 Conflict if duplicate name.

    Example:
        >>> # PATCH /api/v1/collections/11111111-2222-3333-4444-555555555555 with {"name": "Updated"}
    """
    data = await CollectionsService.update(db, user.id, collection_id, dto)
    return BaseResponse(success=True, data=data)


@router.delete(
    "/{collection_id}",
    summary="Delete an owner-scoped collection",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_collection(
    db: DbSessionDep,
    user: CurrentUserDep,
    collection_id: Annotated[uuid.UUID, Path(description="Target collection unique identifier")],
) -> Response:
    """Deletes an owned collection and cleans up exclusive vocabulary items.

    Args:
        db (AsyncSession): Active database session dependency.
        user (User): Authenticated user dependency.
        collection_id (uuid.UUID): Target collection unique identifier.

    Returns:
        Response: HTTP 204 No Content upon successful deletion.

    Raises:
        AppException: 404 Not Found if collection is missing or not owned by user.

    Example:
        >>> # DELETE /api/v1/collections/11111111-2222-3333-4444-555555555555
    """
    await CollectionsService.delete(db, user.id, collection_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{collection_id}/items", summary="List saved vocabulary in an owner-scoped collection")
async def get_collection_items(
    db: DbSessionDep,
    user: CurrentUserDep,
    collection_id: Annotated[uuid.UUID, Path(description="Target collection unique identifier")],
    query: Annotated[GetCollectionItemsQueryDto, Depends()],
) -> BaseResponse[CollectionItemsListDataDto]:
    """Retrieves paginated vocabulary items within an owned collection.

    Args:
        db (AsyncSession): Active database session dependency.
        user (User): Authenticated user dependency.
        collection_id (uuid.UUID): Target collection unique identifier.
        query (GetCollectionItemsQueryDto): Filtering and pagination query parameters.

    Returns:
        BaseResponse[CollectionItemsListDataDto]: Envelope enclosing collection items and metadata.

    Raises:
        AppException: 404 Not Found if collection is missing or not owned by user.

    Example:
        >>> # GET /api/v1/collections/11111111-2222-3333-4444-555555555555/items?page=1&limit=20
    """
    data = await CollectionsService.find_items(db, user.id, collection_id, query)
    return BaseResponse(success=True, data=data)


@router.post(
    "/{collection_id}/items",
    summary="Bulk add saved vocabulary to a collection",
    status_code=status.HTTP_201_CREATED,
)
async def add_collection_items(
    db: DbSessionDep,
    user: CurrentUserDep,
    collection_id: Annotated[uuid.UUID, Path(description="Target collection unique identifier")],
    dto: AddCollectionItemsDto,
) -> BaseResponse[CollectionItemsAddDataDto]:
    """Bulk associates saved vocabulary items to an owned collection.

    Args:
        db (AsyncSession): Active database session dependency.
        user (User): Authenticated user dependency.
        collection_id (uuid.UUID): Target collection unique identifier.
        dto (AddCollectionItemsDto): Vocabulary IDs list payload.

    Returns:
        BaseResponse[CollectionItemsAddDataDto]: Count of newly added items.

    Raises:
        AppException: 404 Not Found if collection is missing or not owned; 422 if vocabulary not owned.

    Example:
        >>> # POST /api/v1/collections/11111111-2222-3333-4444-555555555555/items with {"userVocabularyIds": [...]}
    """
    data = await CollectionsService.add_items(db, user.id, collection_id, dto)
    return BaseResponse(success=True, data=data)


@router.delete(
    "/{collection_id}/items/{user_vocabulary_id}",
    summary="Remove vocabulary from collection",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_collection_item(
    db: DbSessionDep,
    user: CurrentUserDep,
    collection_id: Annotated[uuid.UUID, Path(description="Target collection unique identifier")],
    user_vocabulary_id: Annotated[uuid.UUID, Path(description="Target saved vocabulary unique identifier")],
) -> Response:
    """Removes a single saved vocabulary relation from an owned collection.

    Args:
        db (AsyncSession): Active database session dependency.
        user (User): Authenticated user dependency.
        collection_id (uuid.UUID): Target collection unique identifier.
        user_vocabulary_id (uuid.UUID): Saved vocabulary unique identifier.

    Returns:
        Response: HTTP 204 No Content upon successful removal.

    Raises:
        AppException: 404 Not Found if collection or membership does not exist.

    Example:
        >>> # DELETE /api/v1/collections/11111111-2222-3333-4444-555555555555/items/22222222-3333-4444-5555-666666666666
    """
    await CollectionsService.delete_item(db, user.id, collection_id, user_vocabulary_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
