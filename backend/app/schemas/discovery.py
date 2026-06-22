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


class LikeIn(BaseModel):
    target_user_id: uuid.UUID


class LikeResult(BaseModel):
    matched: bool
    match_id: uuid.UUID | None = None
