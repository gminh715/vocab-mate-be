# Vocab Mate Backend  Python Edition

A high-performance Python backend for **Vocab Mate**, replacing the NestJS backend while maintaining 100% API contract and feature parity with the frontend.

## Tech Stack

- **Framework**: FastAPI (ASGI) + Uvicorn
- **Validation**: Pydantic v2 + Pydantic Settings
- **Database**: PostgreSQL with asyncpg + SQLAlchemy 2.0 (Async) + Alembic
- **Spaced Repetition**: `fsrs` (Py-FSRS 6.x)
- **AI Providers**: Google GenAI SDK (`google-genai`) + Groq SDK (`groq`)
- **NLP & Parsing**: NLTK + BeautifulSoup4 + lxml
- **Authentication**: PyJWT + pwdlib/bcrypt + HttpOnly Cookie rotation
- **Package Manager**: `uv`

---

## Directory Structure

```text
vocab-mate-backend-python/
+-- app/
   +-- main.py                     # FastAPI application entrypoint & middleware
   +-- core/
      +-- config.py               # Pydantic Settings (.env loader)
      +-- database.py             # AsyncEngine, AsyncSessionLocal, Base
      +-- security.py             # Password hashing, JWT encode/decode
   +-- common/
      +-- response.py             # Standard success envelope: { success: True, data, meta }
      +-- exceptions.py           # Error envelope: { success: False, error: {...} }
      +-- deps.py                 # Common dependencies (get_db)
   +-- models/                     # SQLAlchemy ORM models (users, articles, tutor, etc.)
   +-- modules/                    # Business feature modules
       +-- auth/                   # Register, login, refresh rotation, logout
       +-- users/                  # Profile, avatars (Cloudinary), admin
       +-- categories/             # Article categories
       +-- articles/               # Article publication, sentence/term segmentation
          +-- helpers/            # Sentence parser, term marker, HTML sanitizer
       +-- news_ingestion/         # The Guardian API client & importer
       +-- vocabularies/           # User vocabulary, CEFR levels
       +-- collections/            # Vocabulary collections
       +-- tutor/                  # FSRS tutor sessions, candidate selector, grading
       +-- reading/                # Reading progress & streaks
       +-- analytics/              # User & admin learning analytics
       +-- ai/                     # Gemini & Groq fallback structured generator
       +-- health/                 # /health/live, /health/ready
+-- alembic/                        # Async database migrations
+-- tests/                          # Pytest test suite
+-- pyproject.toml                  # Dependencies and project metadata
+-- .env.example                    # Environment variable template
```

---

## Quickstart

### 1. Environment Setup
Copy the example environment file and configure secrets:
```powershell
cp .env.example .env
```

### 2. Start Development Server
```powershell
uv run python -m uvicorn app.main:app --reload --port 3000
```
- API Base: `http://localhost:3000`
- Swagger UI Documentation: `http://localhost:3000/api/docs`
- ReDoc Documentation: `http://localhost:3000/api/redoc`

### 3. Run Migrations
```powershell
uv run python -m alembic upgrade head
```

### 4. Run Tests
```powershell
uv run python -m pytest
```
