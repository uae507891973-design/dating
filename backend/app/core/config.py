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

    # JWT
    jwt_secret: str = "change-me-in-prod"  # переопределяется в окружении
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_min: int = 30
    jwt_refresh_ttl_days: int = 30

    # OTP (SMS-код подтверждения)
    otp_backend: str = "redis"  # redis | memory (memory — для тестов/локально)
    otp_length: int = 4
    otp_ttl_sec: int = 300            # срок жизни кода
    otp_max_attempts: int = 5          # попыток ввода на один код
    otp_request_window_sec: int = 3600  # окно лимита запросов
    otp_request_max: int = 5            # макс. запросов кода на телефон в окне

    # Безопасность / возрастной ценз
    min_user_age: int = 18

    # Версии юридических документов (152-ФЗ)
    consent_privacy_version: str = "1.0"
    consent_terms_version: str = "1.0"

    @property
    def is_prod(self) -> bool:
        return self.environment == "prod"


@lru_cache
def get_settings() -> Settings:
    """Кэшированный доступ к настройкам."""
    return Settings()
