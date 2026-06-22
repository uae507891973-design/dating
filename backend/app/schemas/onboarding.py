"""Схемы онбординга и теста совместимости."""

from pydantic import BaseModel, Field

from app.models.profile import Intent
from app.models.psychotest import Importance


class OptionOut(BaseModel):
    value: int
    label: str


class QuestionOut(BaseModel):
    id: str
    category: str
    text: str
    ordered: bool
    options: list[OptionOut]


class AnswerIn(BaseModel):
    question_id: str
    value: int
    importance: Importance = Importance.medium


class TestSubmitIn(BaseModel):
    answers: list[AnswerIn] = Field(min_length=1)
    intent: Intent


class OnboardingStatusOut(BaseModel):
    test_completed: bool
    answered_count: int
    total_questions: int
    intent: Intent | None = None
    psychoprofile: dict[str, float] = {}
