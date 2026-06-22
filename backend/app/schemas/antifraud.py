"""Схемы антифрода."""

import uuid

from pydantic import BaseModel


class RiskFlagOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    risk_score: int
    reasons: list[str]
    status: str


class AssessmentOut(BaseModel):
    user_id: uuid.UUID
    risk_score: int
    trust_score: int
    reasons: list[str]
