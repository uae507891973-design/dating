"""Хранилище медиа (локальное на фундаменте; объектное хранилище РФ — далее).

Интерфейс save_photo не меняется при замене бэкенда на S3-совместимое
хранилище РФ — переключение прозрачно для остального кода.
"""

import uuid
from pathlib import Path

from app.core.config import get_settings

settings = get_settings()

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}


class UnsupportedImageError(ValueError):
    """Содержимое файла не является поддерживаемым изображением."""


def detect_image_ext(content: bytes) -> str | None:
    """Определить формат по сигнатуре (magic bytes). None — если не изображение."""
    if content[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return ".webp"
    return None


def save_photo(user_id: uuid.UUID, filename: str, content: bytes) -> str:
    """Сохранить файл и вернуть его URL.

    Формат определяется по сигнатуре содержимого (не по расширению имени),
    чтобы нельзя было залить не-изображение с картиночным расширением.
    """
    ext = detect_image_ext(content)
    if ext is None:
        raise UnsupportedImageError("file is not a supported image")
    name = f"{uuid.uuid4().hex}{ext}"

    user_dir = Path(settings.media_dir) / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / name).write_bytes(content)

    return f"{settings.media_base_url}/{user_id}/{name}"
