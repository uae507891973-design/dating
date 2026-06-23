"""Схемы уведомлений и устройств."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.notification import NotificationType


class DeviceIn(BaseModel):
    token: str = Field(min_length=8, max_length=255)
    platform: str = Field(pattern="^(ios|android|web)$")


class NotificationOut(BaseModel):
    id: uuid.UUID
    type: NotificationType
    payload: dict
    is_read: bool
    created_at: datetime
