from __future__ import annotations

import logging
import os
from pathlib import Path
from dotenv import load_dotenv

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env file to ensure environment variables are available for AI providers
load_dotenv()


class Settings(BaseSettings):
    """Central typed settings for the application."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Logging
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level: DEBUG, INFO, WARNING, ERROR",
    )

    # Storage & Limits
    IMAGE_STORAGE_DIR: Path = Field(
        default=Path("./storage/images"),
        description="Filesystem directory where uploaded image blobs are stored",
    )
    MAX_IMAGE_SIZE_MB: int = Field(
        default=5,
        description="Maximum allowed image size in Megabytes",
    )
    DATABASE_URL: str = Field(
        default="sqlite:///./storage/lostfound.db",
        description="Database connection string",
    )

    # HTTP API Server
    HTTP_HOST: str = Field(
        default="0.0.0.0",
        description="Host to bind HTTP server",
    )
    HTTP_PORT: int = Field(
        default=8000,
        description="Port for HTTP server",
    )

    # AI Provider Settings
    OPENAI_API_KEY: str | None = Field(
        default=None,
        description="OpenAI API key",
    )
    ANTHROPIC_API_KEY: str | None = Field(
        default=None,
        description="Anthropic API key",
    )
    GOOGLE_API_KEY: str | None = Field(
        default=None,
        description="Google Gemini API key",
    )
    LLM_PROVIDER: str = Field(
        default="anthropic",
        description="anthropic | openai | gemini",
    )
    LLM_MODEL: str = Field(
        default="claude-sonnet-4-6",
        description="Provider-specific model ID",
    )
    EMBEDDING_PROVIDER: str = Field(
        default="openai",
        description="openai | gemini",
    )
    EMBEDDING_MODEL: str = Field(
        default="text-embedding-3-small",
        description="Embedding model ID",
    )

    # Robustness / Retries
    AI_MAX_RETRIES: int = Field(
        default=3,
        description="Maximum retry attempts on transient AI failures",
    )
    AI_RETRY_MIN_WAIT: float = Field(
        default=1.0,
        description="Initial retry backoff wait in seconds",
    )
    AI_RETRY_MAX_WAIT: float = Field(
        default=8.0,
        description="Max retry backoff wait in seconds",
    )

    # Offline Mode
    OFFLINE_MODE: bool = Field(
        default=False,
        description="Disable AI processing for testing/demo purposes",
    )

    @property
    def max_image_size_bytes(self) -> int:
        """Calculate maximum image size in bytes."""
        return self.MAX_IMAGE_SIZE_MB * 1024 * 1024


settings = Settings()


def ensure_ai_provider_env() -> None:
    """Ensure environment variables are set for AI providers to use os.getenv()."""
    if settings.OPENAI_API_KEY:
        os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
    if settings.ANTHROPIC_API_KEY:
        os.environ["ANTHROPIC_API_KEY"] = settings.ANTHROPIC_API_KEY
    if settings.GOOGLE_API_KEY:
        os.environ["GOOGLE_API_KEY"] = settings.GOOGLE_API_KEY
    os.environ["LLM_PROVIDER"] = settings.LLM_PROVIDER
    os.environ["LLM_MODEL"] = settings.LLM_MODEL
    os.environ["EMBEDDING_PROVIDER"] = settings.EMBEDDING_PROVIDER
    os.environ["EMBEDDING_MODEL"] = settings.EMBEDDING_MODEL


def configure_logging() -> None:
    """Configure structured root logging according to configured LOG_LEVEL."""
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
