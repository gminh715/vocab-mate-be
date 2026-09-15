"""Authentication service handling registration, login, token rotation, and credential lifecycles."""

import asyncio
import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, Response, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.models.enums import UserRole, UserStatus
from app.models.users import RefreshSession, User
from app.modules.auth.schemas import (
    AccessTokenDataDto,
    AuthDataDto,
    ChangePasswordDto,
    LoginDto,
    RegisterDto,
)
from app.modules.users.schemas import PublicUserDto

DUMMY_PASSWORD_HASH = "$2b$12$C6UzMDM.H6dfI/f/IKcEe.3pKBm5M7zKYYCq6VqvJ7uY2wK7jI0wS"
INVALID_CREDENTIALS_MSG = "Invalid email or password"


class AuthService:
    """Core service managing user authentication, sessions, and credential lifecycle."""

    @staticmethod
    def hash_token(raw: str) -> str:
        """Computes SHA-256 hex digest of a raw token string.

        Args:
            raw (str): Raw token string.

        Returns:
            str: 64-character hex digest.

        Example:
            >>> h = AuthService.hash_token("token_jti_123")
            >>> len(h)
            64
        """
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @classmethod
    async def create_tokens(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        user_role: UserRole,
        replaced_by_session_id: uuid.UUID | None = None,
    ) -> tuple[str, str]:
        """Issues an access token and a refresh session with secure rotation tracking.

        Args:
            db (AsyncSession): Active database session.
            user_id (uuid.UUID): Authenticated user ID.
            user_role (UserRole): Role assigned to the user.
            replaced_by_session_id (uuid.UUID | None, optional): Old session ID being rotated. Defaults to None.

        Returns:
            tuple[str, str]: Pair of (access_token_jwt, refresh_token_jwt).

        Example:
            >>> # access_token, refresh_token = await AuthService.create_tokens(db, user.id, user.role)
        """
        # 1. Generate Access Token
        access_payload = {
            "sub": str(user_id),
            "role": user_role.value if hasattr(user_role, "value") else str(user_role),
            "type": "access",
            "exp": datetime.now(UTC) + timedelta(seconds=settings.JWT_ACCESS_EXPIRES_IN),
        }
        access_token = jwt.encode(access_payload, settings.JWT_ACCESS_SECRET, algorithm="HS256")

        # 2. Generate Refresh Token & Session
        jti = str(uuid.uuid4())
        refresh_payload = {
            "sub": str(user_id),
            "jti": jti,
            "type": "refresh",
            "exp": datetime.now(UTC) + timedelta(seconds=settings.JWT_REFRESH_EXPIRES_IN),
        }
        refresh_token = jwt.encode(refresh_payload, settings.JWT_REFRESH_SECRET, algorithm="HS256")

        # Persist session in DB
        new_session = RefreshSession(
            id=uuid.uuid4(),
            user_id=user_id,
            token_hash=cls.hash_token(jti),
            expires_at=datetime.now(UTC) + timedelta(seconds=settings.JWT_REFRESH_EXPIRES_IN),
        )
        db.add(new_session)
        await db.flush()

        # Mark rotation link if replacing old session
        if replaced_by_session_id:
            await db.execute(
                update(RefreshSession)
                .where(RefreshSession.id == replaced_by_session_id)
                .values(
                    revoked_at=datetime.now(UTC),
                    replaced_by_session_id=new_session.id,
                )
            )

        await db.commit()
        return access_token, refresh_token

    @classmethod
    async def register(
        cls,
        db: AsyncSession,
        dto: RegisterDto,
        response: Response,
    ) -> AuthDataDto:
        """Registers a new user account with hashed password and issues an initial JWT token pair.

        Args:
            db (AsyncSession): Active database session.
            dto (RegisterDto): Registration request payload.
            response (Response): FastAPI response object for setting HttpOnly refresh cookie.

        Returns:
            AuthDataDto: Public user profile and bearer access token.

        Raises:
            HTTPException: 409 if the email address is already registered.

        Example:
            >>> # auth_data = await AuthService.register(db, reg_dto, response)
        """
        email_clean = dto.email.strip().lower()

        # Check existing email
        stmt = select(User).where(User.email == email_clean)
        res = await db.execute(stmt)
        if res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email is already registered",
            )

        password_hash = await asyncio.to_thread(get_password_hash, dto.password)
        new_user = User(
            id=uuid.uuid4(),
            email=email_clean,
            password_hash=password_hash,
            display_name=dto.displayName.strip(),
            preferred_language=dto.preferredLanguage,
            role=UserRole.USER,
            status=UserStatus.ACTIVE,
            daily_study_minutes=10,
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)

        access_token, refresh_token = await cls.create_tokens(db, new_user.id, new_user.role)
        cls.set_cookie(response, refresh_token)

        return AuthDataDto(
            user=PublicUserDto.model_validate(new_user),
            accessToken=access_token,
        )

    @classmethod
    async def login(
        cls,
        db: AsyncSession,
        dto: LoginDto,
        response: Response,
    ) -> AuthDataDto:
        """Authenticates user credentials with constant-time protections against email enumeration.

        Args:
            db (AsyncSession): Active database session.
            dto (LoginDto): Login credentials payload.
            response (Response): FastAPI response object for setting HttpOnly refresh cookie.

        Returns:
            AuthDataDto: Authenticated user profile and bearer access token.

        Raises:
            HTTPException: 401 if credentials do not match any active account.
            HTTPException: 403 if the user account is suspended or disabled.

        Example:
            >>> # auth_data = await AuthService.login(db, login_dto, response)
        """
        email_clean = dto.email.strip().lower()

        stmt = select(User).where(User.email == email_clean)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()

        if not user:
            await asyncio.to_thread(verify_password, dto.password, DUMMY_PASSWORD_HASH)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=INVALID_CREDENTIALS_MSG,
            )

        if not await asyncio.to_thread(verify_password, dto.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=INVALID_CREDENTIALS_MSG,
            )

        if user.status != UserStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is suspended or disabled",
            )

        user.last_login_at = datetime.now(UTC)
        await db.commit()

        access_token, refresh_token = await cls.create_tokens(db, user.id, user.role)
        cls.set_cookie(response, refresh_token)

        return AuthDataDto(
            user=PublicUserDto.model_validate(user),
            accessToken=access_token,
        )

    @classmethod
    async def refresh(
        cls,
        db: AsyncSession,
        refresh_payload: dict,
        response: Response,
    ) -> AccessTokenDataDto:
        """Rotates the refresh session and returns a new access token.

        Args:
            db (AsyncSession): Active database session.
            refresh_payload (dict): Validated refresh claims dictionary extracted from cookie.
            response (Response): FastAPI response object for setting new rotated refresh cookie.

        Returns:
            AccessTokenDataDto: Newly generated access token.

        Raises:
            HTTPException: 401 if session is missing, expired, or user is inactive.
            HTTPException: 403 if refresh token was already revoked or re-used.

        Example:
            >>> # token_data = await AuthService.refresh(db, payload, response)
        """
        user_id = uuid.UUID(refresh_payload["sub"])
        jti = refresh_payload["jti"]
        token_hash = cls.hash_token(jti)

        # Look up session
        stmt = select(RefreshSession).where(RefreshSession.token_hash == token_hash)
        res = await db.execute(stmt)
        session_rec = res.scalar_one_or_none()

        if not session_rec:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh session not found",
            )

        if session_rec.revoked_at is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Refresh token was revoked or already used",
            )

        if session_rec.expires_at < datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh session has expired",
            )

        # Look up user
        u_stmt = select(User).where(User.id == user_id)
        u_res = await db.execute(u_stmt)
        user = u_res.scalar_one_or_none()
        if not user or user.status != UserStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account inactive or missing",
            )

        # Rotate token
        access_token, new_refresh_token = await cls.create_tokens(
            db, user.id, user.role, replaced_by_session_id=session_rec.id
        )
        cls.set_cookie(response, new_refresh_token)

        return AccessTokenDataDto(accessToken=access_token)

    @classmethod
    async def logout(
        cls,
        db: AsyncSession,
        current_user: User,
        refresh_payload: dict | None,
        response: Response,
    ) -> None:
        """Revokes current refresh session and clears cookie.

        Args:
            db (AsyncSession): Active database session.
            current_user (User): Authenticated user requesting logout.
            refresh_payload (dict | None): Optional decoded refresh token claims.
            response (Response): FastAPI response object to clear refresh cookie.

        Example:
            >>> # await AuthService.logout(db, user, refresh_payload, response)
        """
        if refresh_payload and "jti" in refresh_payload:
            token_hash = cls.hash_token(refresh_payload["jti"])
            await db.execute(
                update(RefreshSession)
                .where(RefreshSession.token_hash == token_hash, RefreshSession.user_id == current_user.id)
                .values(revoked_at=datetime.now(UTC))
            )
            await db.commit()

        cls.clear_cookie(response)

    @classmethod
    async def change_password(
        cls,
        db: AsyncSession,
        current_user: User,
        dto: ChangePasswordDto,
        response: Response,
    ) -> None:
        """Modifies account password for the authenticated user and revokes active sessions.

        Args:
            db (AsyncSession): Active database session.
            current_user (User): Authenticated user modifying password.
            dto (ChangePasswordDto): Change password payload containing current and new password.
            response (Response): FastAPI response object to clear refresh cookie.

        Raises:
            HTTPException: 400 if current password verification fails.

        Example:
            >>> # await AuthService.change_password(db, user, change_dto, response)
        """
        if not await asyncio.to_thread(verify_password, dto.currentPassword, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password does not match",
            )

        current_user.password_hash = await asyncio.to_thread(get_password_hash, dto.newPassword)
        # Invalidate all active refresh sessions on password change
        await db.execute(
            update(RefreshSession)
            .where(RefreshSession.user_id == current_user.id, RefreshSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        await db.commit()
        cls.clear_cookie(response)

    @staticmethod
    def set_cookie(response: Response, refresh_token: str) -> None:
        """Sets the HttpOnly refresh token cookie on the outgoing response.

        Args:
            response (Response): FastAPI response object.
            refresh_token (str): Encoded refresh JWT token string.
        """
        response.set_cookie(
            key="refreshToken",
            value=refresh_token,
            max_age=settings.JWT_REFRESH_EXPIRES_IN,
            path="/api/v1/auth",
            httponly=True,
            secure=settings.COOKIE_SECURE,
            samesite=settings.COOKIE_SAME_SITE,
        )

    @staticmethod
    def clear_cookie(response: Response) -> None:
        """Clears the HttpOnly refresh token cookie on the outgoing response.

        Args:
            response (Response): FastAPI response object.
        """
        response.delete_cookie(
            key="refreshToken",
            path="/api/v1/auth",
            httponly=True,
            secure=settings.COOKIE_SECURE,
            samesite=settings.COOKIE_SAME_SITE,
        )
