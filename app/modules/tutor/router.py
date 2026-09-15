"""FastAPI router for the Tutor module managing daily study sessions, quizzes, and FSRS grading."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, status

from app.common.deps import CurrentUserDep, DbSessionDep
from app.common.response import BaseResponse
from app.modules.tutor.schemas import (
    SubmitAnswerDto,
    SubmitAnswerResponseDataDto,
    TodayStatusDataDto,
    TutorHistoryDataDto,
    TutorHistoryQueryDto,
    TutorSessionDetailDataDto,
    TutorSessionWithItemDataDto,
)
from app.modules.tutor.service import TutorService

router = APIRouter(prefix="/api/v1/tutor-sessions", tags=["Tutor"])
tutor_service = TutorService()


@router.get("/today", summary="Get today's tutor session status, readiness, and due count")
async def get_today_status(
    db: DbSessionDep,
    user: CurrentUserDep,
) -> BaseResponse[TodayStatusDataDto]:
    """Calculates whether a session can be started or resumed for today's study date in Asia/Ho_Chi_Minh.

    Args:
        db (AsyncSession): Active database session dependency.
        user (User): Authenticated learner user dependency.

    Returns:
        BaseResponse[TodayStatusDataDto]: Standard response envelope enclosing session readiness status.

    Example:
        >>> # GET /api/v1/tutor-sessions/today
    """
    data = await tutor_service.get_today_status(db, user.id)
    return BaseResponse(success=True, data=data)


@router.post("", summary="Start a new daily tutor session or resume an active one")
async def start_or_resume_session(
    db: DbSessionDep,
    user: CurrentUserDep,
) -> BaseResponse[TutorSessionWithItemDataDto]:
    """Creates a new session for today if none exists, or returns the existing ACTIVE session and question.

    Args:
        db (AsyncSession): Active database session dependency.
        user (User): Authenticated learner user dependency.

    Returns:
        BaseResponse[TutorSessionWithItemDataDto]: Enclosing session state and current pending activity item.

    Example:
        >>> # POST /api/v1/tutor-sessions
    """
    data = await tutor_service.start_or_resume_session(db, user.id)
    return BaseResponse(success=True, data=data)


@router.get("/history", summary="Get paginated history of tutor sessions")
async def get_history(
    db: DbSessionDep,
    user: CurrentUserDep,
    query: Annotated[TutorHistoryQueryDto, Depends()],
) -> BaseResponse[TutorHistoryDataDto]:
    """Returns completed and historical tutor sessions using cursor-based keyset pagination.

    Args:
        db (AsyncSession): Active database session dependency.
        user (User): Authenticated learner user dependency.
        query (TutorHistoryQueryDto): Keyset cursor and limit parameters.

    Returns:
        BaseResponse[TutorHistoryDataDto]: Enclosing paginated list of sessions and next cursor.

    Example:
        >>> # GET /api/v1/tutor-sessions/history?limit=10
    """
    data = await tutor_service.get_history(db, user.id, query)
    return BaseResponse(success=True, data=data)


@router.get("/{sessionId}", summary="Get tutor session state, current activity, or completion summary")
async def get_session(
    db: DbSessionDep,
    user: CurrentUserDep,
    sessionId: Annotated[uuid.UUID, Path(description="Tutor session unique identifier")],
) -> BaseResponse[TutorSessionWithItemDataDto]:
    """Retrieves the session by ID with its pending activity item or completion statistics.

    Args:
        db (AsyncSession): Active database session dependency.
        user (User): Authenticated learner user dependency.
        sessionId (uuid.UUID): Target session identifier.

    Returns:
        BaseResponse[TutorSessionWithItemDataDto]: Enclosing active question or summary stats.

    Example:
        >>> # GET /api/v1/tutor-sessions/550e8400-e29b-41d4-a716-446655440000
    """
    data = await tutor_service.get_session(db, user.id, sessionId)
    return BaseResponse(success=True, data=data)


@router.get("/{sessionId}/detail", summary="Get full session review with all answered questions and explanations")
async def get_session_detail(
    db: DbSessionDep,
    user: CurrentUserDep,
    sessionId: Annotated[uuid.UUID, Path(description="Tutor session unique identifier")],
) -> BaseResponse[TutorSessionDetailDataDto]:
    """Retrieves full session history exposing user answers, canonical correct answers, and explanations.

    Args:
        db (AsyncSession): Active database session dependency.
        user (User): Authenticated learner user dependency.
        sessionId (uuid.UUID): Target session identifier.

    Returns:
        BaseResponse[TutorSessionDetailDataDto]: Enclosing all answered items and performance summary.

    Example:
        >>> # GET /api/v1/tutor-sessions/550e8400-e29b-41d4-a716-446655440000/detail
    """
    data = await tutor_service.get_session_detail(db, user.id, sessionId)
    return BaseResponse(success=True, data=data)


@router.post(
    "/{sessionId}/items/{itemId}/answers",
    summary="Submit an answer for the current pending activity item",
    status_code=status.HTTP_200_OK,
)
async def submit_answer(
    db: DbSessionDep,
    user: CurrentUserDep,
    sessionId: Annotated[uuid.UUID, Path(description="Tutor session unique identifier")],
    itemId: Annotated[uuid.UUID, Path(description="Target activity item unique identifier")],
    dto: SubmitAnswerDto,
) -> BaseResponse[SubmitAnswerResponseDataDto]:
    """Grades the answer deterministically, updates FSRS card parameters atomically, and returns feedback.

    Args:
        db (AsyncSession): Active database session dependency.
        user (User): Authenticated learner user dependency.
        sessionId (uuid.UUID): Target session identifier.
        itemId (uuid.UUID): Target activity item identifier.
        dto (SubmitAnswerDto): Answer payload.

    Returns:
        BaseResponse[SubmitAnswerResponseDataDto]: Enclosing item grading result and updated session status.

    Example:
        >>> # POST /api/v1/tutor-sessions/.../items/.../answers with {"answer": "A"}
    """
    data = await tutor_service.submit_answer(db, user.id, sessionId, itemId, dto)
    return BaseResponse(success=True, data=data)


@router.post("/{sessionId}/abandon", summary="Abandon an active tutor session")
async def abandon_session(
    db: DbSessionDep,
    user: CurrentUserDep,
    sessionId: Annotated[uuid.UUID, Path(description="Tutor session unique identifier")],
) -> BaseResponse[TutorSessionWithItemDataDto]:
    """Terminates the session early and marks any pending items as SKIPPED.

    Args:
        db (AsyncSession): Active database session dependency.
        user (User): Authenticated learner user dependency.
        sessionId (uuid.UUID): Target session identifier.

    Returns:
        BaseResponse[TutorSessionWithItemDataDto]: Enclosing abandoned session state and final summary stats.

    Example:
        >>> # POST /api/v1/tutor-sessions/550e8400-e29b-41d4-a716-446655440000/abandon
    """
    data = await tutor_service.abandon_session(db, user.id, sessionId)
    return BaseResponse(success=True, data=data)
