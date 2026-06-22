"""Авто-модерация фото (NSFW).

На фундаменте классификатор — детерминированная заглушка (по содержимому/имени),
чтобы отрабатывать все ветки модерации. Реальная модель (AI NSFW-классификатор)
подключается через classify_nsfw без изменения логики порогов.
"""

from app.core.config import get_settings
from app.models.photo import ModerationStatus

settings = get_settings()


def classify_nsfw(content: bytes, filename: str = "") -> float:
    """Вернуть NSFW-score 0..1 (заглушка; в проде — ML-модель)."""
    haystack = (filename or "").lower()
    marker = content[:64].lower() if content else b""
    if "nsfw" in haystack or b"nsfw" in marker:
        return 0.95
    if "review" in haystack or b"review" in marker:
        return 0.6
    return 0.05


def decide(score: float) -> tuple[ModerationStatus, str | None]:
    """Решение по NSFW-score с учётом порогов."""
    if score >= settings.nsfw_reject_threshold:
        return ModerationStatus.rejected, "Откровенный контент запрещён"
    if score >= settings.nsfw_review_threshold:
        return ModerationStatus.pending, "Отправлено на ручную проверку"
    return ModerationStatus.approved, None
