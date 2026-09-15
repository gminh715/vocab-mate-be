"""Common FastAPI dependencies for database sessions, authentication, and token payloads."""

from typing import Annotated, Any

import jwt
from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_token
from app.models.enums import UserRole, UserStatus
from app.models.users import User

security_bearer = HTTPBearer(auto_error=False)

DbSessionDep = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    db: DbSessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_bearer)],
) -> User:
    """Extracts and authenticates the user from the Bearer JWT token.

    Args:
        db (AsyncSession): Active asynchronous database session.
        credentials (HTTPAuthorizationCredentials | None): Bearer credentials from request.

    Returns:
        User: Authenticated User database entity.

    Raises:
        HTTPException: 401 if missing, invalid, or expired token; 403 if account is disabled.

    Example:
        >>> # Dependency injection usage in FastAPI path operation:
        >>> # async def get_profile(user: CurrentUserDep):
        >>> #     return user.display_name
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
        )

    payload = decode_token(credentials.credentials, settings.JWT_ACCESS_SECRET)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        )

    user_id_raw = payload.get("sub")
    if not user_id_raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
        )
    try:
        import uuid as _uuid

        user_id = _uuid.UUID(str(user_id_raw))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID format in token",
        ) from None

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
        )

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended or disabled",
        )

    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


async def get_current_admin(current_user: CurrentUserDep) -> User:
    """Asserts that the authenticated caller has the ADMIN role.

    Args:
        current_user (User): The resolved authenticated user.

    Returns:
        User: Authenticated admin user entity.

    Raises:
        HTTPException: 403 if the user is not an administrator.

    Example:
        >>> # Dependency injection usage in admin router:
        >>> # async def delete_item(admin: CurrentAdminDep):
        >>> #     ...
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required",
        )
    return current_user


CurrentAdminDep = Annotated[User, Depends(get_current_admin)]


async def get_refresh_token_payload(
    refreshToken: Annotated[str | None, Cookie()] = None,
) -> dict[str, Any]:
    """Extracts and validates the refresh token from the HttpOnly cookie.

    Args:
        refreshToken (str | None, optional): Raw JWT token string. Defaults to None.

    Returns:
        dict[str, Any]: Decoded claims dictionary.

    Raises:
        HTTPException: 401 if cookie is missing or token is invalid.

    Example:
        >>> # Used to extract refresh session in auth controller:
        >>> # async def refresh(payload: RefreshTokenPayloadDep):
        >>> #     ...
    """
    if not refreshToken:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token cookie missing",
        )

    try:
        payload = jwt.decode(
            refreshToken,
            settings.JWT_REFRESH_SECRET,
            algorithms=["HS256"],
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from None

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    return payload


RefreshTokenPayloadDep = Annotated[dict[str, Any], Depends(get_refresh_token_payload)]
