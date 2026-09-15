"""FastAPI router for the Vocabularies module managing saved terms."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response, status

from app.common.deps import CurrentUserDep, DbSessionDep
from app.common.response import BaseResponse
from app.modules.vocabularies.schemas import (
    GetVocabulariesQueryDto,
    SaveVocabularyDto,
    VocabularyDetailDataDto,
    VocabularyListDataDto,
    VocabularySaveDataDto,
)
from app.modules.vocabularies.service import VocabulariesService

router = APIRouter(prefix="/api/v1/vocabularies", tags=["Vocabularies"])


@router.get("", summary="List the authenticated user saved vocabulary")
async def get_vocabularies(
    db: DbSessionDep,
    user: CurrentUserDep,
    query: Annotated[GetVocabulariesQueryDto, Depends()],
) -> BaseResponse[VocabularyListDataDto]:
    """Retrieves paginated and filtered saved vocabulary snapshots.

    Args:
        db (AsyncSession): Active database session dependency.
        user (User): Authenticated learner user dependency.
        query (GetVocabulariesQueryDto): Filter and pagination parameters.

    Returns:
        BaseResponse[VocabularyListDataDto]: Standard response envelope enclosing vocabulary items and pagination meta.

    Example:
        >>> # GET /api/v1/vocabularies?page=1&limit=20&cefrLevel=B2
    """
    data = await VocabulariesService.find_all(db, user.id, query)
    return BaseResponse(success=True, data=data)


@router.post("", summary="Save an eligible contextual term snapshot", status_code=status.HTTP_201_CREATED)
async def save_vocabulary(
    db: DbSessionDep,
    user: CurrentUserDep,
    dto: SaveVocabularyDto,
) -> BaseResponse[VocabularySaveDataDto]:
    """Captures a contextual term occurrence as an immutable vocabulary snapshot.

    Args:
        db (AsyncSession): Active database session dependency.
        user (User): Authenticated learner user dependency.
        dto (SaveVocabularyDto): Contextual term reference and optional target collection IDs.

    Returns:
        BaseResponse[VocabularySaveDataDto]: Envelope enclosing created vocabulary snapshot and memberships.

    Raises:
        AppException: If term is not found, not active, not approved, or already saved by learner.

    Example:
        >>> # POST /api/v1/vocabularies with {"articleSentenceTermId": "..."}
    """
    data = await VocabulariesService.save(db, user.id, dto)
    return BaseResponse(success=True, data=data)


@router.get("/{user_vocabulary_id}", summary="Get an owner-scoped saved vocabulary snapshot")
async def get_vocabulary(
    db: DbSessionDep,
    user: CurrentUserDep,
    user_vocabulary_id: Annotated[uuid.UUID, Path(description="Target saved vocabulary UUID identifier")],
) -> BaseResponse[VocabularyDetailDataDto]:
    """Retrieves an owner-scoped saved vocabulary snapshot with associated collections and article context.

    Args:
        db (AsyncSession): Active database session dependency.
        user (User): Authenticated learner user dependency.
        user_vocabulary_id (uuid.UUID): Target saved vocabulary unique identifier.

    Returns:
        BaseResponse[VocabularyDetailDataDto]: Envelope enclosing vocabulary detail and source article metadata.

    Raises:
        AppException: If item is not found or not owned by calling user.

    Example:
        >>> # GET /api/v1/vocabularies/11111111-2222-3333-4444-555555555555
    """
    data = await VocabulariesService.find_one(db, user.id, user_vocabulary_id)
    return BaseResponse(success=True, data=data)


@router.delete(
    "/{user_vocabulary_id}",
    summary="Delete a saved vocabulary snapshot",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_vocabulary(
    db: DbSessionDep,
    user: CurrentUserDep,
    user_vocabulary_id: Annotated[uuid.UUID, Path(description="Target saved vocabulary UUID identifier")],
) -> Response:
    """Deletes an owner-scoped saved vocabulary snapshot by ID.

    Args:
        db (AsyncSession): Active database session dependency.
        user (User): Authenticated learner user dependency.
        user_vocabulary_id (uuid.UUID): Target saved vocabulary unique identifier.

    Returns:
        Response: HTTP 204 No Content upon successful deletion.

    Raises:
        AppException: If item is not found or not owned by calling user.

    Example:
        >>> # DELETE /api/v1/vocabularies/11111111-2222-3333-4444-555555555555
    """
    await VocabulariesService.remove(db, user.id, user_vocabulary_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
