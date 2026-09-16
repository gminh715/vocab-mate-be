#!/bin/sh
set -e

echo "==> [Vocab Mate] Running database migrations (alembic)..."
alembic upgrade head

echo "==> [Vocab Mate] Starting FastAPI application on port ${PORT:-3000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-3000}" --workers "${UVICORN_WORKERS:-2}"
