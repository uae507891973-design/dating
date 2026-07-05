"""Схемы юридических документов."""

from pydantic import BaseModel


class LegalDocOut(BaseModel):
    type: str
    version: str
    title: str
    url: str
    required: bool


class ReconsentIn(BaseModel):
    accepted_documents: list[str]
