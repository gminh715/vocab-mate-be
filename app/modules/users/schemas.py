"""User profile and administration Data Transfer Objects (DTOs)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CefrLevel, UserRole, UserStatus


class PublicUserDto(BaseModel):
    """Publicly visible user summary."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: UserRole
    status: UserStatus


class MyAccountDto(PublicUserDto):
    """Detailed learner account profile and personalized learning settings."""

    displayName: str
    avatarUrl: str | None = None
    currentCefrLevel: CefrLevel | None = None
    learningGoal: str | None = None
    preferredLanguage: str = "vi"
    dailyStudyMinutes: int = 10


class UpdateMyProfileDto(BaseModel):
    """Payload for updating user profile and learning goal preferences."""

    displayName: str | None = Field(None, min_length=1, max_length=100)
    avatarUrl: str | None = None
    currentCefrLevel: CefrLevel | None = None
    learningGoal: CefrLevel | None = None
    preferredLanguage: str | None = Field(None, pattern="^(vi|en)$")
    dailyStudyMinutes: int | None = Field(None, ge=5, le=120)


class AdminUserDto(MyAccountDto):
    """Administrative user entity with audit and login timestamps."""

    createdAt: datetime
    updatedAt: datetime
    lastLoginAt: datetime | None = None


class AdminUpdateStatusDto(BaseModel):
    """Payload for administrative account status mutation."""

    status: UserStatus


class AdminUpdateRoleDto(BaseModel):
    """Payload for administrative role promotion or demotion."""

    role: UserRole
