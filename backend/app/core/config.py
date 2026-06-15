"""Конфигурация приложения (pydantic-settings)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки сервиса, читаются из переменных окружения / .env."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Общее
    app_name: str = "epic-davinci"
    environment: str = "dev"  # dev | stage | prod
    debug: bool = True
    log_level: str = "INFO"

    # База данных (async-драйвер)
    database_url: str = (
        "postgresql+asyncpg://davinci:davinci@localhost:5432/davinci"
    )

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Безопасность / возрастной ценз
    min_user_age: int = 18

    @property
    def is_prod(self) -> bool:
        return self.environment == "prod"


@lru_cache
def get_settings() -> Settings:
    """Кэшированный доступ к настройкам."""
    return Settings()
