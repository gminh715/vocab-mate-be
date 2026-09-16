# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

# Install system dependencies (curl for container healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy uv binary from Astral's official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Environment configurations
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PORT=3000 \
    NLTK_DATA="/app/nltk_data"

WORKDIR /app

# Step 1: Install Python dependencies first (leverages Docker layer cache)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Step 2: Add virtualenv to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Step 3: Download NLTK datasets needed for CEFR Lexical Analyzer
RUN mkdir -p /app/nltk_data && \
    python -m nltk.downloader -d /app/nltk_data punkt punkt_tab averaged_perceptron_tagger averaged_perceptron_tagger_eng wordnet

# Step 4: Copy application source code and migrations
COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY app/ ./app/

# Step 5: Install project package
RUN uv sync --frozen --no-dev

# Step 6: Copy entrypoint script and normalize line endings
COPY entrypoint.sh ./entrypoint.sh
RUN sed -i 's/\r$//' ./entrypoint.sh && chmod +x ./entrypoint.sh

# Step 7: Create and switch to non-root user for security
RUN useradd -u 1000 -m -s /bin/sh appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 3000

ENTRYPOINT ["./entrypoint.sh"]
