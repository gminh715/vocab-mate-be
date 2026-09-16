# Vocab Mate API — Backend

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Asyncpg-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%20Async-D71F00)](https://www.sqlalchemy.org/)
[![Py-FSRS](https://img.shields.io/badge/FSRS-v6.3-orange)](https://github.com/open-spaced-repetition/py-fsrs)
[![AI Models](https://img.shields.io/badge/AI-Gemini%203.5%20Flash%20Lite%20%7C%20Groq-4285F4)](https://ai.google.dev/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Asynchronous REST API powering **Vocab Mate** — an adaptive English reading and vocabulary learning platform featuring automated news ingestion, CEFR level classification, and AI-driven spaced repetition practice.

---

## Tech Stack

- **Runtime & Framework**: Python 3.12+, FastAPI 0.141, Uvicorn (ASGI)
- **Database & ORM**: PostgreSQL via `asyncpg`, SQLAlchemy 2.0 (Async), Alembic migrations
- **AI Engine**: Primary **Google Gemini** (`gemini-3.5-flash-lite`), Fallback **Groq** (`openai/gpt-oss-20b`)
- **Spaced Repetition**: Py-FSRS 6.3 (Free Spaced Repetition Scheduler)
- **NLP & Parsing**: NLTK (CEFR tokenization & POS tagging), BeautifulSoup4, lxml
- **Auth & Storage**: JWT (access token) + HttpOnly cookie rotation (refresh token), bcrypt, Cloudinary
- **Package Manager**: `uv`

---

## Features

- **Multi-Provider AI Resilience**: Primary Gemini with minimal thinking config, automatically falling back to Groq strict JSON schema mode on rate limits or errors.
- **Adaptive Tutor (FSRS 6.3)**: 4 exercise formats (Multiple Choice, Cloze, Sentence Construction, Definition Matching) with deterministic server-side grading.
- **Automated Journalism Ingestion**: Fetches authentic articles from The Guardian API, cleans HTML, and classifies CEFR word levels (A1–C2).
- **Secure Authentication**: Short-lived JWTs, rotated HttpOnly refresh cookies, and bcrypt hashing.

---

## Quickstart

### Prerequisites
- Python `>=3.12` and [`uv`](https://github.com/astral-sh/uv)
- PostgreSQL database (local or Supabase)

### 1. Setup Environment
```bash
cp .env.example .env
# Edit .env with your DATABASE_URL, GEMINI_API_KEY, GROQ_API_KEY, etc.
```

### 2. Install & Download NLTK Datasets
```bash
uv sync
uv run python -m nltk.downloader punkt punkt_tab averaged_perceptron_tagger averaged_perceptron_tagger_eng wordnet
```

### 3. Run Migrations & Start Server
```bash
# Run database migrations
uv run alembic upgrade head

# Start development server (http://localhost:3000)
uv run python -m uvicorn app.main:app --reload --port 3000
```

- **Interactive Swagger UI**: [http://localhost:3000/api/docs](http://localhost:3000/api/docs)
- **ReDoc**: [http://localhost:3000/api/redoc](http://localhost:3000/api/redoc)

---

## Docker Setup

Run full-stack (Backend + Frontend) with a single command:

```bash
docker compose up --build -d
```

- **Liveness Probe**: `GET http://localhost:3000/health/live`
- **Readiness Probe**: `GET http://localhost:3000/health/ready`

---

## Environment Variables

| Variable | Default / Example | Description |
| :--- | :--- | :--- |
| `PORT` | `3000` | Server listening port |
| `DATABASE_URL` | `postgresql+asyncpg://...` | Async PostgreSQL connection URI |
| `DIRECT_URL` | `postgresql://...` | Sync connection URI for Alembic |
| `JWT_ACCESS_SECRET` | *(Random string)* | Secret for signing access tokens (15m) |
| `JWT_REFRESH_SECRET`| *(Random string)* | Secret for signing refresh tokens (7d) |
| `CORS_ORIGIN` | `http://localhost:5173,...` | Allowed CORS origins |
| `GEMINI_API_KEY` | *(Your Key)* | Google AI Studio key |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Primary Gemini model |
| `GROQ_API_KEY` | *(Your Key)* | Groq Cloud key |
| `GROQ_MODEL` | `openai/gpt-oss-20b` | Fallback Groq model |
| `GUARDIAN_API_KEY` | *(Your Key)* | The Guardian Content API key |
| `CLOUDINARY_*` | *(Credentials)* | Cloudinary credentials for avatars |

---

## Project Structure

```text
vocab-mate-backend-python/
├── alembic/                # Database migrations
├── app/
│   ├── common/             # Exceptions, dependencies, and response envelope
│   ├── core/               # Config (.env), Database engine, Security
│   ├── models/             # SQLAlchemy ORM models
│   ├── modules/            # Domain modules (auth, users, articles, tutor, ai, etc.)
│   └── main.py             # FastAPI entrypoint & middleware
├── tests/                  # Pytest test suite
├── Dockerfile              # Production multi-stage Docker build
├── docker-compose.yml      # Container orchestration
└── pyproject.toml          # Project dependencies & tool configs
```

---

## Testing & Linting

```bash
uv run pytest          # Run test suite
uv run ruff check .    # Lint checks
uv run ruff format .   # Code formatting
```

---

## License

[MIT License](LICENSE)
