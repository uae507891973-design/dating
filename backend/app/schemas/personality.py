"""Схемы теста «Кто вы в паре?»."""

from pydantic import BaseModel, Field


class POptionOut(BaseModel):
    id: str
    label: str


class PQuestionOut(BaseModel):
    id: str
    text: str
    options: list[POptionOut]


class PTestMetaOut(BaseModel):
    title: str
    disclaimer: str
    questions: list[PQuestionOut]


class PAnswerIn(BaseModel):
    question_id: str
    option_id: str


class PSubmitIn(BaseModel):
    answers: list[PAnswerIn] = Field(min_length=1)
    add_to_profile: bool = True


class ArchetypeOut(BaseModel):
    key: str
    title: str
    emoji: str
    short: str
    description: str
    strengths: list[str]
    in_pair: str
    disclaimer: str
    scores: dict[str, int] = {}
    in_profile: bool = False
