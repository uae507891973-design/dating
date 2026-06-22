"""Схемы верификации, жалоб, блокировок и аудита."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.safety import VerificationStatus


class VerificationOut(BaseModel):
    status: VerificationStatus
    is_verified: bool


class ReportIn(BaseModel):
    target_user_id: uuid.UUID
    reason: str = Field(min_length=1, max_length=500)


class ReportOut(BaseModel):
    id: uuid.UUID
    status: str


class BlockIn(BaseModel):
    target_user_id: uuid.UUID


class AuditOut(BaseModel):
    actor_id: uuid.UUID | None
    action: str
    target: str | None
    created_at: datetime
