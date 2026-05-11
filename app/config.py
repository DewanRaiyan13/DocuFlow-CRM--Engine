"""
Centralized configuration via Pydantic Settings.

All values are read from environment variables or a `.env` file.
This single source of truth keeps secrets out of the codebase and
makes the app 12-Factor compliant.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Core ───────────────────────────────────────────────────────────
    APP_NAME: str = "DocuFlow-CRM"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENV: Literal["development", "staging", "production"] = "development"
    API_V1_PREFIX: str = "/api/v1"

    # ── Database ───────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://docuflow:docuflow@localhost:5432/docuflow"
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10

    # ── Redis / Celery ─────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── File Watcher ───────────────────────────────────────────────────
    WATCH_DIRECTORY: str = "./watch_directory"
    SUPPORTED_EXTENSIONS: list[str] = [".pdf", ".docx"]

    # ── LLM Configuration ─────────────────────────────────────────────
    LLM_PROVIDER: Literal["claude", "gemini", "openai"] = "claude"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "claude-sonnet-4-20250514"
    LLM_MAX_TOKENS: int = 4096
    LLM_TEMPERATURE: float = 0.1

    # ── Intelligence ───────────────────────────────────────────────────
    STALE_LEAD_THRESHOLD_DAYS: int = 14

    # ── S3 (Optional) ─────────────────────────────────────────────────
    S3_ENABLED: bool = False
    S3_BUCKET_NAME: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_REGION: str = "us-east-1"

    @property
    def watch_path(self) -> Path:
        """Resolve watch directory to an absolute Path."""
        return Path(self.WATCH_DIRECTORY).resolve()


@lru_cache
def get_settings() -> Settings:
    """Cached singleton – avoids re-parsing env vars on every call."""
    return Settings()
