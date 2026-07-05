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

    # CORS (список origin для web-клиента; пусто = запросы только same-origin)
    cors_origins: list[str] = []

    # Общие лимиты действий (rate-limit)
    ratelimit_backend: str = "redis"    # redis | memory
    like_rate_max: int = 100            # лайков в окно
    like_rate_window_sec: int = 60
    message_rate_max: int = 60          # сообщений в окно
    message_rate_window_sec: int = 60

    # Видеосессии: авто-истечение
    video_request_ttl_sec: int = 120    # «requested» без принятия — истекает
    video_max_active_sec: int = 900     # макс. длительность активного звонка

    # Присутствие: считать пользователя онлайн N секунд после активности
    online_window_sec: int = 300

    # Шифрование ПДн в покое (152-ФЗ); в prod обязателен свой длинный секрет.
    pii_secret: str = "dev-pii-secret-change-me"

    # JWT
    jwt_secret: str = "change-me-in-prod"  # переопределяется в окружении
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_min: int = 30
    jwt_refresh_ttl_days: int = 30

    # OTP (SMS-код подтверждения)
    otp_backend: str = "redis"  # redis | memory (memory — для тестов/локально)
    otp_debug_log: bool = False  # логировать код в dev (НИКОГДА не включать в prod)
    otp_length: int = 6
    otp_ttl_sec: int = 300            # срок жизни кода
    otp_max_attempts: int = 5          # попыток ввода на один код
    otp_request_window_sec: int = 3600  # окно лимита запросов
    otp_request_max: int = 5            # макс. запросов кода на телефон в окне
    otp_ip_window_sec: int = 3600       # окно лимита по IP
    otp_ip_max: int = 30               # макс. запросов кода с одного IP в окне

    # Безопасность / возрастной ценз
    min_user_age: int = 18

    # Медиа / хранилище фото
    media_dir: str = "media"
    # Приватное хранилище файлов верификации (селфи/документ) — НЕ раздаётся статикой.
    verify_media_dir: str = "verify_media"
    media_base_url: str = "/media"
    photo_max_bytes: int = 10 * 1024 * 1024  # 10 МБ
    max_photos_per_user: int = 6

    # Модерация контента (NSFW): пороги score 0..1
    nsfw_reject_threshold: float = 0.8   # выше — авто-отклонение
    nsfw_review_threshold: float = 0.4   # выше — в ручную очередь

    # Антифрод: пороги поведенческих сигналов
    antifraud_window_sec: int = 3600
    antifraud_msg_velocity: int = 20        # сообщений за окно
    antifraud_like_velocity: int = 60       # лайков за окно
    antifraud_duplicate_threshold: int = 5  # одинаковых сообщений
    antifraud_reports_threshold: int = 3    # открытых жалоб на пользователя
    antifraud_flag_threshold: int = 50      # risk-score для авто-флага

    # Видеознакомство «вслепую»
    video_duration_sec: int = 180           # длительность звонка (3 минуты)
    video_default_blur: float = 1.0         # стартовый уровень блюра (1.0 — макс.)
    video_trust_bonus: int = 5              # бонус к trust-score за живой контакт

    # Версии юридических документов (152-ФЗ)
    consent_privacy_version: str = "1.0"
    consent_terms_version: str = "1.0"
    consent_marketing_version: str = "1.0"

    @property
    def is_prod(self) -> bool:
        return self.environment == "prod"


@lru_cache
def get_settings() -> Settings:
    """Кэшированный доступ к настройкам."""
    return Settings()
