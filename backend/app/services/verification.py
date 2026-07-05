"""Верификация профиля: селфи + документ.

Файлы сохраняются в приватное хранилище (verify_media_dir), которое НЕ
монтируется как статика — доступ только у модерации. Liveness-проверка селфи
на фундаменте — заглушка; реальная (движение/поворот) подключается через
check_selfie без изменения флоу.
"""

import uuid
from pathlib import Path

from app.core.config import get_settings

settings = get_settings()


def check_selfie(content: bytes, filename: str = "") -> bool:
    """True — предварительная liveness-проверка пройдена (заглушка)."""
    if not content:
        return False
    haystack = (filename or "").lower()
    marker = content[:64].lower()
    if "fail" in haystack or b"fail" in marker:
        return False
    return True


def save_private(user_id: uuid.UUID, kind: str, content: bytes, ext: str) -> str:
    """Сохранить файл проверки приватно; вернуть путь (не URL)."""
    user_dir = Path(settings.verify_media_dir) / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    name = f"{kind}-{uuid.uuid4().hex}{ext}"
    path = user_dir / name
    path.write_bytes(content)
    return str(path)
