"""Authentication endpoints for user registration, login, token refresh, and credential lifecycle."""

from fastapi import APIRouter, Request, Response, status

from app.common.deps import (
    CurrentUserDep,
    DbSessionDep,
    RefreshTokenPayloadDep,
    get_refresh_token_payload,
)
from app.common.response import BaseResponse
from app.modules.auth.schemas import (
    AccessTokenDataDto,
    AuthDataDto,
    ChangePasswordDto,
    LoginDto,
    MessageDataDto,
    RegisterDto,
)
from app.modules.auth.service import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register a USER account with initial learning settings",
)
async def register(
    db: DbSessionDep,
    dto: RegisterDto,
    response: Response,
) -> BaseResponse[AuthDataDto]:
    """Registers a new user account with default learning preferences and issues initial tokens.

    Args:
        db (AsyncSession): Active database session dependency.
        dto (RegisterDto): Registration data transfer object.
        response (Response): FastAPI response to attach HttpOnly refresh cookie.

    Returns:
        BaseResponse[AuthDataDto]: Enclosing authenticated user profile and access token.

    Example:
        >>> # POST /api/v1/auth/register with RegisterDto JSON payload
    """
    data = await AuthService.register(db, dto, response)
    return BaseResponse(success=True, data=data)


@router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    summary="Log in with email and password",
)
async def login(
    db: DbSessionDep,
    dto: LoginDto,
    response: Response,
) -> BaseResponse[AuthDataDto]:
    """Authenticates user credentials, generates tokens, and sets the HttpOnly refresh cookie.

    Args:
        db (AsyncSession): Active database session dependency.
        dto (LoginDto): Login data transfer object.
        response (Response): FastAPI response to attach HttpOnly refresh cookie.

    Returns:
        BaseResponse[AuthDataDto]: Enclosing authenticated user profile and access token.

    Example:
        >>> # POST /api/v1/auth/login with LoginDto JSON payload
    """
    data = await AuthService.login(db, dto, response)
    return BaseResponse(success=True, data=data)


@router.post(
    "/refresh",
    status_code=status.HTTP_200_OK,
    summary="Issue a new access token using a refresh token",
)
async def refresh(
    db: DbSessionDep,
    refresh_payload: RefreshTokenPayloadDep,
    response: Response,
) -> BaseResponse[AccessTokenDataDto]:
    """Reads the refreshToken HttpOnly cookie and rotates it.

    Args:
        db (AsyncSession): Active database session dependency.
        refresh_payload (dict[str, Any]): Decoded claims from the HttpOnly refresh cookie.
        response (Response): FastAPI response to attach new rotated HttpOnly refresh cookie.

    Returns:
        BaseResponse[AccessTokenDataDto]: Enclosing newly minted access token.

    Example:
        >>> # POST /api/v1/auth/refresh with HttpOnly refreshToken cookie
    """
    data = await AuthService.refresh(db, refresh_payload, response)
    return BaseResponse(success=True, data=data)


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Log out and clear the refresh-token cookie",
)
async def logout(
    db: DbSessionDep,
    current_user: CurrentUserDep,
    request: Request,
    response: Response,
) -> BaseResponse[MessageDataDto]:
    """Revokes the current refresh session and clears the refresh-token cookie.

    Args:
        db (AsyncSession): Active database session dependency.
        current_user (User): Authenticated user requesting logout.
        request (Request): Incoming HTTP request to inspect cookies.
        response (Response): FastAPI response to delete HttpOnly cookie.

    Returns:
        BaseResponse[MessageDataDto]: Confirmation message envelope.

    Example:
        >>> # POST /api/v1/auth/logout with Authorization header and refreshToken cookie
    """
    refresh_payload = None
    try:
        raw_cookie = request.cookies.get("refreshToken")
        if raw_cookie:
            refresh_payload = await get_refresh_token_payload(raw_cookie)
    except Exception:
        pass

    await AuthService.logout(db, current_user, refresh_payload, response)
    return BaseResponse(success=True, data=MessageDataDto(message="Thao tác thành công."))


@router.patch(
    "/change-password",
    status_code=status.HTTP_200_OK,
    summary="Change the authenticated account password",
)
async def change_password(
    db: DbSessionDep,
    current_user: CurrentUserDep,
    dto: ChangePasswordDto,
    response: Response,
) -> BaseResponse[MessageDataDto]:
    """Modifies account password for the authenticated user and invalidates current refresh cookies.

    Args:
        db (AsyncSession): Active database session dependency.
        current_user (User): Authenticated user changing password.
        dto (ChangePasswordDto): Change password payload.
        response (Response): FastAPI response to delete HttpOnly cookie.

    Returns:
        BaseResponse[MessageDataDto]: Confirmation message envelope.

    Example:
        >>> # PATCH /api/v1/auth/change-password with currentPassword and newPassword
    """
    await AuthService.change_password(db, current_user, dto, response)
    return BaseResponse(success=True, data=MessageDataDto(message="Thao tác thành công."))
