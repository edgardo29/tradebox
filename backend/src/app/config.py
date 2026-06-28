"""Backend settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Runtime settings for the FastAPI backend."""

    database_url: str = Field(
        default="postgresql+psycopg://tradebox_user:tradebox_password@localhost:5432/tradebox_db_dev",
        validation_alias="DATABASE_URL",
    )

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached backend settings."""

    return Settings()


settings = get_settings()
