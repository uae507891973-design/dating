"""Схемы анкеты и фото."""

import uuid
from datetime import date

from pydantic import BaseModel, Field

from app.models.photo import ModerationStatus
from app.models.profile import Gender, Intent


class ProfileIn(BaseModel):
    display_name: str | None = Field(default=None, max_length=80)
    birth_date: date | None = None
    gender: Gender | None = None
    looking_for: Gender | None = None
    intent: Intent | None = None
    city: str | None = Field(default=None, max_length=120)
    bio: str | None = Field(default=None, max_length=2000)


class ProfileOut(BaseModel):
    display_name: str | None
    birth_date: date | None
    gender: Gender | None
    looking_for: Gender | None
    intent: Intent | None
    city: str | None
    bio: str | None
    is_verified: bool = False


class PhotoOut(BaseModel):
    id: uuid.UUID
    url: str
    is_primary: bool
    moderation_status: ModerationStatus
    moderation_reason: str | None = None


class ModerationDecisionIn(BaseModel):
    decision: ModerationStatus  # approved | rejected
    reason: str | None = Field(default=None, max_length=255)


class ModerationPhotoOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    url: str
    moderation_status: ModerationStatus
    nsfw_score: float | None
