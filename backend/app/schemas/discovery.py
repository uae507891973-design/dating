"""Схемы подбора."""

import uuid

from pydantic import BaseModel


class CandidateOut(BaseModel):
    user_id: uuid.UUID
    display_name: str | None
    city: str | None
    bio: str | None
    primary_photo_url: str | None
    is_verified: bool
    score: int               # совместимость 0..100
    common_questions: int
    reasons: list[str] = []  # «Почему вы подходите» (объяснимый мэтчинг)
    is_online: bool = False
    video_state: str = "offline"  # available | offline | disabled


class DirectMessageIn(BaseModel):
    target_user_id: uuid.UUID
    body: str


class DirectMessageOut(BaseModel):
    match_id: uuid.UUID
    message_id: uuid.UUID


class CategoryPreferenceIn(BaseModel):
    category: str
    importance: str  # muted | normal | important


class CategoryPreferenceOut(BaseModel):
    category: str
    importance: str


class LikeIn(BaseModel):
    target_user_id: uuid.UUID


class LikeResult(BaseModel):
    matched: bool
    match_id: uuid.UUID | None = None
