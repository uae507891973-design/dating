"""Схемы юридических документов."""

from pydantic import BaseModel


class LegalDocOut(BaseModel):
    type: str
    version: str
    title: str
    url: str
    required: bool
