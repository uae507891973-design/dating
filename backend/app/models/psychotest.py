"""Модели теста совместимости: ответы и психопрофиль."""

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin


class Importance(str, enum.Enum):
    """Важность вопроса для пользователя (вес при подсчёте совместимости)."""

    low = "low"
    medium = "medium"
    high = "high"


IMPORTANCE_WEIGHT: dict[Importance, int] = {
    Importance.low: 1,
    Importance.medium: 2,
    Importance.high: 3,
}


class PsychotestAnswer(Base, TimestampMixin):
    __tablename__ = "psychotest_answers"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # question_id — стабильный код вопроса из каталога (app/services/psychotest.py)
    question_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[int] = mapped_column(Integer, nullable=False)
    importance: Mapped[Importance] = mapped_column(
        Enum(Importance, name="importance"),
        default=Importance.medium,
        nullable=False,
    )


class Psychoprofile(Base, TimestampMixin):
    __tablename__ = "psychoprofiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # vector: { category -> нормализованное среднее (0..1) }
    vector: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
