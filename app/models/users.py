"""SQLAlchemy ORM models representing user accounts and refresh token sessions."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CHAR,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import CefrLevel, UserRole, UserStatus


class User(Base):
    """User account model matching PostgreSQL 'users' table.

    Attributes:
        id (uuid.UUID): Primary key UUID.
        email (str): Case-insensitive unique login email.
        password_hash (str): Bcrypt-hashed password string.
        role (UserRole): Authorization role (ADMIN, USER).
        status (UserStatus): Account state (ACTIVE, SUSPENDED, DISABLED).
        last_login_at (datetime | None): Timestamp of last successful authentication.
        display_name (str): User visible name.
        avatar_url (str | None): Cloudinary or hosted avatar URL.
        current_cefr_level (CefrLevel | None): Estimated learner CEFR proficiency level.
        learning_goal (str | None): Target CEFR learning goal.
        preferred_language (str): Preferred interface language.
        daily_study_minutes (int): Targeted daily review time in minutes.
        created_at (datetime): Account creation timestamp.
        updated_at (datetime): Profile last update timestamp.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    email: Mapped[str] = mapped_column(CITEXT, unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole, name="user_role", create_type=False),
        default=UserRole.USER,
        nullable=False,
    )
    status: Mapped[UserStatus] = mapped_column(
        SQLEnum(UserStatus, name="user_status", create_type=False),
        default=UserStatus.ACTIVE,
        nullable=False,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_cefr_level: Mapped[CefrLevel | None] = mapped_column(
        SQLEnum(CefrLevel, name="cefr_level", create_type=False),
        nullable=True,
    )
    learning_goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(20), default="vi", nullable=False)
    daily_study_minutes: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    refresh_sessions = relationship("RefreshSession", back_populates="user", cascade="all, delete-orphan")
    vocabularies = relationship("UserVocabulary", back_populates="user")
    collections = relationship("VocabularyCollection", back_populates="user")
    tutor_sessions = relationship("TutorSession", back_populates="user")
    article_progress = relationship("UserArticleProgress", back_populates="user")


class RefreshSession(Base):
    """Session record storing hashed refresh tokens for secure rotation.

    Attributes:
        id (uuid.UUID): Primary key UUID.
        user_id (uuid.UUID): Foreign key reference to User ID.
        token_hash (str): SHA-256 hash of the unique JWT jti claim.
        created_at (datetime): Session issuance timestamp.
        expires_at (datetime): Session expiry timestamp.
        revoked_at (datetime | None): Timestamp when rotated or revoked.
        replaced_by_session_id (uuid.UUID | None): Pointer to replacement session upon rotation.
    """

    __tablename__ = "refresh_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(CHAR(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("refresh_sessions.id", ondelete="SET NULL"),
        unique=True,
        nullable=True,
    )

    user = relationship("User", back_populates="refresh_sessions")
