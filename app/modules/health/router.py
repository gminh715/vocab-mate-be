"""Health check endpoints for application liveness and database readiness probes."""

from fastapi import APIRouter, status
from sqlalchemy import text

from app.common.deps import DbSessionDep

router = APIRouter(tags=["Health"])


@router.get("/health/live", status_code=status.HTTP_200_OK)
async def live() -> dict[str, str]:
    """Provides a basic liveness probe confirming the HTTP server is responsive.

    Returns:
        dict[str, str]: Basic status mapping {"status": "ok"}.

    Example:
        >>> # GET /health/live -> {"status": "ok"}
    """
    return {"status": "ok"}


@router.get("/health/ready", status_code=status.HTTP_200_OK)
async def ready(db: DbSessionDep) -> dict[str, str]:
    """Provides a readiness probe verifying active PostgreSQL database connectivity.

    Args:
        db (AsyncSession): Active database session dependency.

    Returns:
        dict[str, str]: Readiness status and database connectivity indicator.

    Example:
        >>> # GET /health/ready -> {"status": "ok", "database": "connected"}
    """
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": str(e)}
