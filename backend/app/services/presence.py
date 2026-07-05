"""Присутствие (онлайн-статус) и доступность видеозвонка."""

from datetime import UTC, datetime

from app.core.config import get_settings
from app.models import Profile, User

settings = get_settings()


def is_online(user: User | None) -> bool:
    """Пользователь онлайн, если был активен в пределах online_window_sec."""
    if user is None or user.last_active_at is None:
        return False
    last = user.last_active_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    return (datetime.now(UTC) - last).total_seconds() <= settings.online_window_sec


def video_state(profile: Profile | None, user: User | None) -> str:
    """Состояние кнопки видеозвонка к данному пользователю.

    - "disabled" — получатель запретил видеозвонки;
    - "offline"  — получатель не в сети (звонок невозможен);
    - "available" — можно звонить.
    """
    if profile is not None and profile.video_calls_enabled is False:
        return "disabled"
    if not is_online(user):
        return "offline"
    return "available"
