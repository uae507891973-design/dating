"""Хранилище медиа (локальное на фундаменте; объектное хранилище РФ — далее).

Интерфейс save_photo не меняется при замене бэкенда на S3-совместимое
хранилище РФ — переключение прозрачно для остального кода.
"""

import uuid
from pathlib import Path

from app.core.config import get_settings

settings = get_settings()

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def save_photo(user_id: uuid.UUID, filename: str, content: bytes) -> str:
    """Сохранить файл и вернуть его URL."""
    ext = Path(filename).suffix.lower() or ".jpg"
    if ext not in ALLOWED_EXT:
        ext = ".jpg"
    name = f"{uuid.uuid4().hex}{ext}"

    user_dir = Path(settings.media_dir) / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / name).write_bytes(content)

    return f"{settings.media_base_url}/{user_id}/{name}"
