"""Схемы согласий (152-ФЗ)."""

from datetime import datetime

from pydantic import BaseModel


class ConsentIn(BaseModel):
    doc_type: str  # privacy | terms
    doc_version: str


class ConsentOut(BaseModel):
    doc_type: str
    doc_version: str
    accepted_at: datetime
