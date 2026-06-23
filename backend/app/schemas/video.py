"""Схемы видеознакомства."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.video import VideoStatus


class VideoSessionOut(BaseModel):
    id: uuid.UUID
    match_id: uuid.UUID
    initiator_id: uuid.UUID
    status: VideoStatus
    blur_level: float
    continue_initiator: bool
    continue_partner: bool
    revealed: bool
    started_at: datetime | None
    ended_at: datetime | None


class BlurIn(BaseModel):
    level: float = Field(ge=0.0, le=1.0)


class ContinueIn(BaseModel):
    yes: bool = True
