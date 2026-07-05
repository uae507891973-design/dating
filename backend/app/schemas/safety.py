"""Схемы верификации, жалоб, блокировок и аудита."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.safety import VerificationStatus


class VerificationOut(BaseModel):
    status: VerificationStatus | None = None  # None — процесс не начат
    is_verified: bool
    selfie_uploaded: bool = False
    document_uploaded: bool = False
    submitted: bool = False  # оба файла загружены, заявка на проверке


class ModerationVerificationOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    status: VerificationStatus
    created_at: datetime


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
