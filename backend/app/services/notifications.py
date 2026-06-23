"""Уведомления: in-app запись + push-доставка (заглушка).

Push отправляется на зарегистрированные устройства пользователя. На фундаменте
доставка логируется; реальный провайдер (FCM/RuStore push) подключается через
send_push без изменения вызовов notify().
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import DeviceToken, Notification
from app.models.notification import NotificationType

logger = get_logger("notifications")


def send_push(token: str, title: str, body: str) -> None:
    """Доставка push (заглушка; в проде — FCM/RuStore push)."""
    logger.info("push_sent", extra={"token": token, "title": title, "body": body})


async def notify(
    db: AsyncSession,
    user_id: uuid.UUID,
    type_: NotificationType,
    payload: dict | None = None,
) -> None:
    """Создать in-app уведомление и отправить push на устройства пользователя.

    Запись добавляется в текущую сессию (commit — на стороне вызывающего).
    """
    payload = payload or {}
    db.add(
        Notification(user_id=user_id, type=type_, payload=payload)
    )
    tokens = (
        await db.execute(
            select(DeviceToken.token).where(DeviceToken.user_id == user_id)
        )
    ).scalars().all()
    title = payload.get("title", type_.value)
    body = payload.get("body", "")
    for token in tokens:
        send_push(token, title, body)
