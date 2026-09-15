"""SQLAlchemy ORM models representing learner vocabulary collections and item memberships."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class VocabularyCollection(Base):
    """User-created vocabulary collection.

    Attributes:
        id (uuid.UUID): Primary key UUID identifier.
        user_id (uuid.UUID): Foreign key reference to owner User ID.
        name (str): User-specified collection folder name.
        created_at (datetime): Database insertion timestamp.
        updated_at (datetime): Last modification timestamp.
    """

    __tablename__ = "vocabulary_collections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="collections")
    items = relationship("VocabularyCollectionItem", back_populates="collection", cascade="all, delete-orphan")


class VocabularyCollectionItem(Base):
    """Membership of a UserVocabulary in a VocabularyCollection.

    Attributes:
        collection_id (uuid.UUID): Composite primary key referencing VocabularyCollection ID.
        user_vocabulary_id (uuid.UUID): Composite primary key referencing UserVocabulary ID.
        added_at (datetime): Timestamp when item was added to collection.
    """

    __tablename__ = "vocabulary_collection_items"

    collection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vocabulary_collections.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_vocabulary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_vocabularies.id", ondelete="CASCADE"),
        primary_key=True,
    )
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    collection = relationship("VocabularyCollection", back_populates="items")
    user_vocabulary = relationship("UserVocabulary", back_populates="collection_items")
