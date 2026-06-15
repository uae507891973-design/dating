"""Сервис аналитики (трекинг событий).

На фундаменте события пишутся в структурный лог. На Стадии 0.3/1 sink
заменяется на ClickHouse по трекинг-плану — интерфейс остаётся прежним.
"""

from typing import Any

from app.core.logging import get_logger

logger = get_logger("analytics")


def track_event(name: str, properties: dict[str, Any] | None = None) -> None:
    """Зафиксировать продуктовое событие по трекинг-плану."""
    logger.info(
        "analytics_event",
        extra={"event": name, "properties": properties or {}},
    )
