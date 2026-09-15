"""Main application module initializing FastAPI, middlewares, exception handlers, and routers."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from time import time

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.common.exceptions import (
    AppException,
    app_exception_handler,
    generic_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.core.config import settings
from app.core.database import engine
from app.modules.analytics.router import admin_router as admin_analytics_router
from app.modules.analytics.router import router as analytics_router
from app.modules.articles.router import admin_router as admin_articles_router
from app.modules.articles.router import router as articles_router
from app.modules.auth.router import router as auth_router
from app.modules.categories.router import admin_router as admin_categories_router
from app.modules.categories.router import router as categories_router
from app.modules.collections.router import router as collections_router
from app.modules.health.router import router as health_router
from app.modules.news_ingestion.router import router as news_ingestion_router
from app.modules.reading.router import router as reading_router
from app.modules.tutor.router import router as tutor_router
from app.modules.users.router import admin_router as admin_users_router
from app.modules.users.router import router as users_router
from app.modules.vocabularies.router import router as vocabularies_router

logger = logging.getLogger("vocab_mate.api")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application startup and graceful shutdown lifecycle.

    Args:
        app (FastAPI): The active FastAPI application instance.

    Yields:
        None: Control back to the application while running.
    """
    logger.info("Starting up Vocab Mate API...")
    yield
    logger.info("Shutting down Vocab Mate API; disposing database engine...")
    await engine.dispose()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="Vocab Mate MVP API (Python)",
    description="REST API for the Vocab Mate learning platform powered by FastAPI",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next) -> Response:
    """Logs incoming HTTP request method, path, status, and latency.

    Args:
        request (Request): Incoming HTTP request.
        call_next (Callable): Next middleware or route handler in chain.

    Returns:
        Response: HTTP response produced by route execution.
    """
    start_time = time()
    response = await call_next(request)
    duration_ms = (time() - start_time) * 1000
    logger.info(
        "%s %s - status=%s duration=%.1fms",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


# Global Exception Handlers for standard response envelope
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(admin_users_router)
app.include_router(categories_router)
app.include_router(admin_categories_router)
app.include_router(collections_router)
app.include_router(vocabularies_router)
app.include_router(articles_router)
app.include_router(admin_articles_router)
app.include_router(reading_router)
app.include_router(news_ingestion_router)
app.include_router(tutor_router)
app.include_router(analytics_router)
app.include_router(admin_analytics_router)


@app.get("/", summary="Root health check and API descriptor")
async def root() -> dict[str, str]:
    """Returns basic API identification and documentation endpoints.

    Returns:
        dict[str, str]: Application metadata mapping.
    """
    return {"name": "Vocab Mate API (Python)", "version": "1.0.0", "docs": "/api/docs"}
