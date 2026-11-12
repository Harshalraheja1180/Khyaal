from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "MemoryCare API"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://memorycare_app:memorycare_dev_password@localhost:5432/memorycare"
    secret_key: str = "development-only-secret-change-before-deployment-000000"
    access_token_minutes: int = 30
    storage_root: Path = PROJECT_ROOT / "storage" / "private"
    max_upload_bytes: int = 10 * 1024 * 1024
    allowed_image_types: str = "image/jpeg,image/png,image/webp"
    allowed_audio_types: str = "audio/mpeg,audio/wav,audio/ogg,audio/webm"
    cors_origins: str = "http://localhost:3000"
    demo_password: str = "DemoCare-Only-Change!"

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator("secret_key")
    @classmethod
    def production_secret_must_be_changed(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("SECRET_KEY must contain at least 32 characters")
        return value

    @field_validator("storage_root", mode="after")
    @classmethod
    def resolve_relative_storage_path(cls, value: Path) -> Path:
        return value if value.is_absolute() else (PROJECT_ROOT / value).resolve()

    @model_validator(mode="after")
    def production_requires_non_default_secret(self) -> "Settings":
        if self.app_env.lower() in {"production", "prod"} and (
            self.secret_key.startswith("development-only") or "replace-this" in self.secret_key.lower()
        ):
            raise ValueError("Set a unique SECRET_KEY before running in production")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def image_type_set(self) -> set[str]:
        return {item.strip().lower() for item in self.allowed_image_types.split(",") if item.strip()}

    @property
    def audio_type_set(self) -> set[str]:
        return {item.strip().lower() for item in self.allowed_audio_types.split(",") if item.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
