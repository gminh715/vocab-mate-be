"""Configuration settings management powered by Pydantic Settings."""

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    """Application runtime settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server Settings
    PORT: int = 3000
    HOST: str = "0.0.0.0"
    ENVIRONMENT: str = "development"

    # Database Settings (PostgreSQL with asyncpg)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/vocab_mate"
    DIRECT_URL: str = "postgresql://postgres:postgres@localhost:5432/vocab_mate"

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def assemble_async_db_url(cls, v: str) -> str:
        """Converts standard postgresql:// URL schema to postgresql+asyncpg:// driver format.

        Args:
            v (str): Raw database connection URI string.

        Returns:
            str: Connection URI compatible with SQLAlchemy AsyncEngine.
        """
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        return v

    # Authentication & JWT
    JWT_ACCESS_SECRET: str = "replace-with-a-long-random-access-secret-at-least-32-chars"
    JWT_ACCESS_EXPIRES_IN: int = 900  # 15 minutes
    JWT_REFRESH_SECRET: str = "replace-with-a-different-long-random-refresh-secret-32-chars"
    JWT_REFRESH_EXPIRES_IN: int = 604800  # 7 days
    BCRYPT_ROUNDS: int = 12

    # CORS & Cookies
    CORS_ORIGIN: str = "http://localhost:5173,http://localhost:3000,https://vocabmate.onrender.com"
    COOKIE_SECURE: bool = False
    COOKIE_SAME_SITE: str = "lax"  # "lax", "strict", or "none"

    # Timezones
    ANALYTICS_TIMEZONE: str = "Asia/Ho_Chi_Minh"

    # AI Service Settings
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    AI_REQUEST_TIMEOUT_MS: int = 30000

    # Guardian Content Ingestion
    GUARDIAN_API_KEY: str = ""
    GUARDIAN_BASE_URL: str = "https://content.guardianapis.com"
    GUARDIAN_REQUEST_TIMEOUT_MS: int = 10000
    GUARDIAN_MAX_RESPONSE_BYTES: int = 2000000
    GUARDIAN_MIN_ARTICLE_CHARACTERS: int = 500

    # Cloudinary Assets
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_SECRET: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_FOLDER: str = "vocab-mate/avatars"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parses comma-separated CORS_ORIGIN string into a list of allowed origins.

        Returns:
            list[str]: Cleaned list of allowed origin URLs.
        """
        return [origin.strip() for origin in self.CORS_ORIGIN.split(",") if origin.strip()]


settings = Settings()
