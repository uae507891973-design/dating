"""Регистрация устройств и in-app уведомления."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import DeviceToken, Notification, User
from app.schemas.notification import DeviceIn, NotificationOut

router = APIRouter(tags=["notifications"])


@router.post("/devices", status_code=204)
async def register_device(
    data: DeviceIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Зарегистрировать push-токен устройства (идемпотентно)."""
    existing = (
        await db.execute(
            select(DeviceToken).where(DeviceToken.token == data.token)
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            DeviceToken(user_id=user.id, token=data.token, platform=data.platform)
        )
    else:
        existing.user_id = user.id
        existing.platform = data.platform
    await db.commit()


@router.get("/notifications", response_model=list[NotificationOut])
async def list_notifications(
    only_unread: bool = False,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[NotificationOut]:
    stmt = select(Notification).where(Notification.user_id == user.id)
    if only_unread:
        stmt = stmt.where(Notification.is_read.is_(False))
    rows = (
        await db.execute(stmt.order_by(desc(Notification.created_at)))
    ).scalars().all()
    return [NotificationOut.model_validate(n, from_attributes=True) for n in rows]


@router.post("/notifications/{notification_id}/read", status_code=204)
async def mark_notification_read(
    notification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    notif = await db.get(Notification, notification_id)
    if notif is None or notif.user_id != user.id:
        raise HTTPException(status_code=404, detail="notification not found")
    notif.is_read = True
    await db.commit()
