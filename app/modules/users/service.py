"""Users management service for user profiles, learning preferences, and administration."""

import asyncio
import uuid
from typing import Any

import cloudinary
import cloudinary.uploader
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.enums import UserRole, UserStatus
from app.models.users import User
from app.modules.users.schemas import (
    AdminUpdateRoleDto,
    AdminUpdateStatusDto,
    AdminUserDto,
    MyAccountDto,
    UpdateMyProfileDto,
)

CEFR_ORDER: dict[str, int] = {
    "A1": 0,
    "A2": 1,
    "B1": 2,
    "B2": 3,
    "C1": 4,
    "C2": 5,
}


class UsersService:
    """Service providing user self-service account management and administrative tools."""

    @staticmethod
    def _map_to_my_account(user: User) -> MyAccountDto:
        return MyAccountDto(
            id=user.id,
            email=user.email,
            role=user.role,
            status=user.status,
            displayName=user.display_name,
            avatarUrl=user.avatar_url,
            currentCefrLevel=user.current_cefr_level,
            learningGoal=user.learning_goal,
            preferredLanguage=user.preferred_language,
            dailyStudyMinutes=user.daily_study_minutes,
        )

    @classmethod
    async def get_me(cls, db: AsyncSession, user_id: uuid.UUID) -> MyAccountDto:
        """Retrieves current account profile by user ID.

        Args:
            db (AsyncSession): Active database session.
            user_id (uuid.UUID): Unique user identifier.

        Returns:
            MyAccountDto: User account representation.

        Raises:
            HTTPException: 404 if the user cannot be found in database.

        Example:
            >>> # account = await UsersService.get_me(db, current_user.id)
            >>> # print(account.email)
        """
        stmt = select(User).where(User.id == user_id)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return cls._map_to_my_account(user)

    @classmethod
    async def update_me(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        dto: UpdateMyProfileDto,
    ) -> MyAccountDto:
        """Updates learning preferences and profile fields for the authenticated user.

        Args:
            db (AsyncSession): Active database session.
            user_id (uuid.UUID): Target user identifier.
            dto (UpdateMyProfileDto): Update payload fields.

        Returns:
            MyAccountDto: Updated user profile.

        Raises:
            HTTPException: 400 if learning goal is lower than current CEFR level or invalid study minutes.
            HTTPException: 404 if the user is not found.

        Example:
            >>> # payload = UpdateMyProfileDto(dailyStudyMinutes=15)
            >>> # updated = await UsersService.update_me(db, user_id, payload)
        """
        stmt = select(User).where(User.id == user_id)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        if dto.dailyStudyMinutes is not None:
            if dto.dailyStudyMinutes not in (5, 10, 15, 20):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Daily study minutes must be one of 5, 10, 15, or 20",
                )
            user.daily_study_minutes = dto.dailyStudyMinutes

        effective_cefr = dto.currentCefrLevel if dto.currentCefrLevel is not None else user.current_cefr_level
        effective_goal = (
            dto.learningGoal.value
            if dto.learningGoal
            else (dto.learningGoal if dto.learningGoal is not None else user.learning_goal)
        )

        if effective_cefr and effective_goal and effective_goal in CEFR_ORDER:
            cefr_key = effective_cefr.value if hasattr(effective_cefr, "value") else str(effective_cefr)
            if CEFR_ORDER[effective_goal] < CEFR_ORDER.get(cefr_key, 0):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Learning goal CEFR level cannot be lower than current CEFR level",
                )

        if dto.displayName is not None:
            user.display_name = dto.displayName.strip()
        if dto.avatarUrl is not None:
            user.avatar_url = dto.avatarUrl
        if dto.currentCefrLevel is not None:
            user.current_cefr_level = dto.currentCefrLevel
        if dto.learningGoal is not None:
            user.learning_goal = dto.learningGoal.value if hasattr(dto.learningGoal, "value") else str(dto.learningGoal)
        if dto.preferredLanguage is not None:
            user.preferred_language = dto.preferredLanguage

        await db.commit()
        await db.refresh(user)
        return cls._map_to_my_account(user)

    @classmethod
    async def upload_avatar(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        file: UploadFile,
    ) -> MyAccountDto:
        """Uploads an avatar file to Cloudinary asynchronously and updates profile.

        Args:
            db (AsyncSession): Active database session.
            user_id (uuid.UUID): Target user identifier.
            file (UploadFile): Uploaded multipart avatar image.

        Returns:
            MyAccountDto: Updated user profile containing the secure avatar URL.

        Raises:
            HTTPException: 400 if MIME type is invalid or file exceeds 5MB.
            HTTPException: 500 if Cloudinary upload fails.

        Example:
            >>> # updated = await UsersService.upload_avatar(db, user_id, upload_file)
        """
        if file.content_type not in ("image/jpeg", "image/png", "image/webp", "image/gif", "image/jpg"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only image files (JPG, PNG, WEBP, GIF) are allowed",
            )

        content = await file.read()
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Avatar file size exceeds maximum limit of 5MB",
            )

        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
        )

        try:
            # Run synchronous Cloudinary upload in threadpool to prevent blocking the event loop
            upload_result = await asyncio.to_thread(
                cloudinary.uploader.upload,
                content,
                folder=settings.CLOUDINARY_FOLDER,
                resource_type="image",
                transformation=[
                    {"width": 300, "height": 300, "crop": "fill", "gravity": "face"},
                    {"quality": "auto", "fetch_format": "auto"},
                ],
            )
            secure_url = upload_result.get("secure_url")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Cloudinary upload failed: {str(e)}",
            ) from e

        return await cls.update_me(db, user_id, UpdateMyProfileDto(avatarUrl=secure_url))

    @classmethod
    async def get_admin_users(
        cls,
        db: AsyncSession,
        page: int = 1,
        limit: int = 20,
        role: UserRole | None = None,
        user_status: UserStatus | None = None,
        search: str | None = None,
    ) -> tuple[list[AdminUserDto], dict[str, Any]]:
        """Lists users with filtering and pagination for administrative views.

        Args:
            db (AsyncSession): Active database session.
            page (int, optional): Current 1-indexed page. Defaults to 1.
            limit (int, optional): Page item limit. Defaults to 20.
            role (UserRole | None, optional): Filter by user role. Defaults to None.
            user_status (UserStatus | None, optional): Filter by user status. Defaults to None.
            search (str | None, optional): Substring search over email and name. Defaults to None.

        Returns:
            tuple[list[AdminUserDto], dict[str, Any]]: List of admin user representations and pagination metadata.

        Example:
            >>> # users, meta = await UsersService.get_admin_users(db, page=1, limit=10)
        """
        stmt = select(User)
        count_stmt = select(func.count()).select_from(User)

        if role:
            stmt = stmt.where(User.role == role)
            count_stmt = count_stmt.where(User.role == role)
        if user_status:
            stmt = stmt.where(User.status == user_status)
            count_stmt = count_stmt.where(User.status == user_status)
        if search and search.strip():
            term = f"%{search.strip()}%"
            stmt = stmt.where(User.email.ilike(term) | User.display_name.ilike(term))
            count_stmt = count_stmt.where(User.email.ilike(term) | User.display_name.ilike(term))

        total_res = await db.execute(count_stmt)
        total = total_res.scalar() or 0

        offset = (page - 1) * limit
        stmt = stmt.order_by(User.created_at.desc()).offset(offset).limit(limit)
        res = await db.execute(stmt)
        users = res.scalars().all()

        user_dtos = [
            AdminUserDto(
                id=u.id,
                email=u.email,
                role=u.role,
                status=u.status,
                displayName=u.display_name,
                avatarUrl=u.avatar_url,
                currentCefrLevel=u.current_cefr_level,
                learningGoal=u.learning_goal,
                preferredLanguage=u.preferred_language,
                dailyStudyMinutes=u.daily_study_minutes,
                createdAt=u.created_at,
                updatedAt=u.updated_at,
                lastLoginAt=u.last_login_at,
            )
            for u in users
        ]

        meta = {
            "page": page,
            "limit": limit,
            "total": total,
            "totalPages": (total + limit - 1) // limit if limit > 0 else 0,
        }
        return user_dtos, meta

    @classmethod
    async def update_user_status(
        cls,
        db: AsyncSession,
        acting_admin_id: uuid.UUID,
        user_id: uuid.UUID,
        dto: AdminUpdateStatusDto,
    ) -> MyAccountDto:
        """Updates user account status with self-lockout and last-admin protections.

        Args:
            db (AsyncSession): Active database session.
            acting_admin_id (uuid.UUID): ID of the administrator performing the action.
            user_id (uuid.UUID): Target user ID.
            dto (AdminUpdateStatusDto): Target status payload.

        Returns:
            MyAccountDto: Updated user representation.

        Raises:
            HTTPException: 404 if target user is not found.
            HTTPException: 409 if admin tries to suspend self or suspend the last active admin.

        Example:
            >>> # updated = await UsersService.update_user_status(db, admin_id, user_id, dto)
        """
        if acting_admin_id == user_id and dto.status in (UserStatus.SUSPENDED, UserStatus.DISABLED):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Administrators cannot suspend or disable their own account",
            )

        stmt = select(User).where(User.id == user_id)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Invariant: Ensure at least one active administrator remains
        if user.role == UserRole.ADMIN and dto.status != UserStatus.ACTIVE:
            count_stmt = (
                select(func.count())
                .select_from(User)
                .where(User.role == UserRole.ADMIN, User.status == UserStatus.ACTIVE, User.id != user_id)
            )
            active_admins = (await db.execute(count_stmt)).scalar() or 0
            if active_admins < 1:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cannot suspend or disable the last active administrator",
                )

        user.status = dto.status
        await db.commit()
        await db.refresh(user)
        return cls._map_to_my_account(user)

    @classmethod
    async def update_user_role(
        cls,
        db: AsyncSession,
        acting_admin_id: uuid.UUID,
        user_id: uuid.UUID,
        dto: AdminUpdateRoleDto,
    ) -> MyAccountDto:
        """Updates user system role with self-demotion and last-admin protections.

        Args:
            db (AsyncSession): Active database session.
            acting_admin_id (uuid.UUID): ID of the administrator performing the action.
            user_id (uuid.UUID): Target user ID.
            dto (AdminUpdateRoleDto): Target role payload.

        Returns:
            MyAccountDto: Updated user representation.

        Raises:
            HTTPException: 404 if target user is not found.
            HTTPException: 409 if admin tries to demote self or remove the last active admin.

        Example:
            >>> # updated = await UsersService.update_user_role(db, admin_id, user_id, dto)
        """
        if acting_admin_id == user_id and dto.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Administrators cannot demote their own account",
            )

        stmt = select(User).where(User.id == user_id)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Invariant: Ensure at least one active administrator remains
        if user.role == UserRole.ADMIN and dto.role != UserRole.ADMIN:
            count_stmt = (
                select(func.count())
                .select_from(User)
                .where(User.role == UserRole.ADMIN, User.status == UserStatus.ACTIVE, User.id != user_id)
            )
            active_admins = (await db.execute(count_stmt)).scalar() or 0
            if active_admins < 1:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cannot demote the last active administrator",
                )

        user.role = dto.role
        await db.commit()
        await db.refresh(user)
        return cls._map_to_my_account(user)
