"""User management HTTP endpoints for profiles, settings, and administration."""

import uuid
from typing import Annotated

from fastapi import APIRouter, File, Query, UploadFile

from app.common.deps import CurrentAdminDep, CurrentUserDep, DbSessionDep
from app.common.response import BaseResponse, ResponseWithMeta
from app.models.enums import UserRole, UserStatus
from app.modules.users.schemas import (
    AdminUpdateRoleDto,
    AdminUpdateStatusDto,
    AdminUserDto,
    MyAccountDto,
    UpdateMyProfileDto,
)
from app.modules.users.service import UsersService

router = APIRouter(prefix="/api/v1/users", tags=["Users"])
admin_router = APIRouter(prefix="/api/v1/admin/users", tags=["Admin Users"])


@router.get("/me", summary="Get the current account and learning settings")
async def get_me(
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> BaseResponse[MyAccountDto]:
    """Retrieves current account profile and learning settings for authenticated caller.

    Args:
        db (AsyncSession): Active database session dependency.
        current_user (User): Authenticated user dependency.

    Returns:
        BaseResponse[MyAccountDto]: Standard response envelope enclosing account profile.

    Example:
        >>> # GET /api/v1/users/me with Authorization Bearer header
    """
    data = await UsersService.get_me(db, current_user.id)
    return BaseResponse(success=True, data=data)


@router.patch("/me", summary="Update the current learning settings")
async def update_me(
    db: DbSessionDep,
    current_user: CurrentUserDep,
    dto: UpdateMyProfileDto,
) -> BaseResponse[MyAccountDto]:
    """Partially updates profile and learning settings owned by the authenticated caller.

    Args:
        db (AsyncSession): Active database session dependency.
        current_user (User): Authenticated user dependency.
        dto (UpdateMyProfileDto): Requested profile updates payload.

    Returns:
        BaseResponse[MyAccountDto]: Standard response envelope enclosing updated profile.

    Example:
        >>> # PATCH /api/v1/users/me with {"dailyStudyMinutes": 15}
    """
    data = await UsersService.update_me(db, current_user.id, dto)
    return BaseResponse(success=True, data=data)


@router.post("/me/avatar", summary="Upload an avatar image for the authenticated user")
async def upload_avatar(
    db: DbSessionDep,
    current_user: CurrentUserDep,
    file: Annotated[UploadFile, File()],
) -> BaseResponse[MyAccountDto]:
    """Uploads an avatar file to Cloudinary and updates profile URL.

    Args:
        db (AsyncSession): Active database session dependency.
        current_user (User): Authenticated user dependency.
        file (UploadFile): Multipart avatar image file.

    Returns:
        BaseResponse[MyAccountDto]: Standard response envelope enclosing updated profile with avatarUrl.

    Example:
        >>> # POST /api/v1/users/me/avatar as multipart/form-data
    """
    data = await UsersService.upload_avatar(db, current_user.id, file)
    return BaseResponse(success=True, data=data)


# ---------------------------------------------------------------------------
# Admin Endpoints
# ---------------------------------------------------------------------------


@admin_router.get("", summary="List all system users (Admin)")
async def list_users(
    db: DbSessionDep,
    admin: CurrentAdminDep,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    role: Annotated[UserRole | None, Query()] = None,
    user_status: Annotated[UserStatus | None, Query(alias="status")] = None,
    search: Annotated[str | None, Query()] = None,
) -> ResponseWithMeta[list[AdminUserDto], dict]:
    """Paginated user directory listing with search and role/status filtering.

    Args:
        db (AsyncSession): Active database session dependency.
        admin (User): Verified administrator user dependency.
        page (int, optional): 1-indexed page number. Defaults to 1.
        limit (int, optional): Maximum items per page. Defaults to 20.
        role (UserRole | None, optional): Filter by account role. Defaults to None.
        user_status (UserStatus | None, optional): Filter by account status. Defaults to None.
        search (str | None, optional): Substring search over email and display name. Defaults to None.

    Returns:
        ResponseWithMeta[list[AdminUserDto], dict]: Paginated list of users and pagination metadata.

    Example:
        >>> # GET /api/v1/admin/users?page=1&limit=20
    """
    users, meta = await UsersService.get_admin_users(
        db, page=page, limit=limit, role=role, user_status=user_status, search=search
    )
    return ResponseWithMeta(success=True, data=users, meta=meta)


@admin_router.patch("/{user_id}/status", summary="Change user account status (Admin)")
async def update_status(
    db: DbSessionDep,
    admin: CurrentAdminDep,
    user_id: uuid.UUID,
    dto: AdminUpdateStatusDto,
) -> BaseResponse[MyAccountDto]:
    """Suspends or reactivates a target user account.

    Args:
        db (AsyncSession): Active database session dependency.
        admin (User): Verified administrator user dependency.
        user_id (uuid.UUID): Target user identifier.
        dto (AdminUpdateStatusDto): New status payload.

    Returns:
        BaseResponse[MyAccountDto]: Standard response envelope enclosing updated profile.

    Example:
        >>> # PATCH /api/v1/admin/users/{user_id}/status with {"status": "SUSPENDED"}
    """
    data = await UsersService.update_user_status(db, admin.id, user_id, dto)
    return BaseResponse(success=True, data=data)


@admin_router.patch("/{user_id}/role", summary="Change user authorization role (Admin)")
async def update_role(
    db: DbSessionDep,
    admin: CurrentAdminDep,
    user_id: uuid.UUID,
    dto: AdminUpdateRoleDto,
) -> BaseResponse[MyAccountDto]:
    """Promotes or demotes target user authorization role.

    Args:
        db (AsyncSession): Active database session dependency.
        admin (User): Verified administrator user dependency.
        user_id (uuid.UUID): Target user identifier.
        dto (AdminUpdateRoleDto): New role payload.

    Returns:
        BaseResponse[MyAccountDto]: Standard response envelope enclosing updated profile.

    Example:
        >>> # PATCH /api/v1/admin/users/{user_id}/role with {"role": "ADMIN"}
    """
    data = await UsersService.update_user_role(db, admin.id, user_id, dto)
    return BaseResponse(success=True, data=data)
