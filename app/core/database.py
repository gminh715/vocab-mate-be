"""Database engine initialization, session factory, and transaction lifecycle helpers."""

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

connect_args: dict[str, Any] = {}
if "supabase.com" in settings.DATABASE_URL or "sslmode=require" in settings.DATABASE_URL:
    connect_args["ssl"] = "require"
    if ":6543" in settings.DATABASE_URL:
        connect_args["prepared_statement_cache_size"] = 0

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=(settings.ENVIRONMENT == "development"),
    future=True,
    pool_pre_ping=True,
    connect_args=connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Declarative Base class for all SQLAlchemy ORM models in Vocab Mate."""

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provides an active asynchronous database session with automatic lifecycle management.

    Yields:
        AsyncSession: Active SQLAlchemy async session.

    Raises:
        Exception: Rolls back transaction and re-raises on any unhandled error.

    Example:
        >>> # Dependency injection in FastAPI endpoint:
        >>> # async def read_items(db: DbSessionDep):
        >>> #     ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
