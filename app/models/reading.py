"""SQLAlchemy ORM model representing user article reading progress and completion states."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UserArticleProgress(Base):
    """User reading progress on an article.

    Attributes:
        id (uuid.UUID): Primary key UUID identifier.
        user_id (uuid.UUID): Foreign key reference to User ID.
        article_id (uuid.UUID): Foreign key reference to Article ID.
        first_opened_at (datetime): Timestamp when reader first opened the article.
        last_read_at (datetime): Timestamp of most recent reading activity.
        completed_at (datetime | None): Timestamp when article reached 100% completion.
        progress_percent (Decimal | None): Reading percentage completion (0.00 to 100.00).
        updated_at (datetime): Last modification timestamp.
    """

    __tablename__ = "user_article_progress"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id"), nullable=False, index=True
    )
    first_opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    progress_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="article_progress")
    article = relationship("Article", back_populates="reader_progress")
