"""Схемы чата."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.message import MessageStatus


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class MessageOut(BaseModel):
    id: uuid.UUID
    match_id: uuid.UUID
    sender_id: uuid.UUID
    body: str
    status: MessageStatus
    created_at: datetime


class MatchOut(BaseModel):
    match_id: uuid.UUID
    other_user_id: uuid.UUID
    other_display_name: str | None
    other_photo_url: str | None
    other_is_verified: bool
    other_is_online: bool = False
    other_video_state: str = "offline"  # available | offline | disabled
    created_at: datetime


class IcebreakersOut(BaseModel):
    suggestions: list[str]
