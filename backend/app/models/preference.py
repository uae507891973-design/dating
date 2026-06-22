"""Предпочтения важности категорий (scrutability)."""

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class FactorImportance(str, enum.Enum):
    muted = "muted"        # категория почти не учитывается
    normal = "normal"
    important = "important"  # повышенный вес


FACTOR_MULTIPLIER: dict[FactorImportance, float] = {
    FactorImportance.muted: 0.25,
    FactorImportance.normal: 1.0,
    FactorImportance.important: 2.0,
}


class CategoryPreference(Base, TimestampMixin):
    """Насколько категория важна пользователю при подборе."""

    __tablename__ = "category_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    category: Mapped[str] = mapped_column(String(32), primary_key=True)
    importance: Mapped[FactorImportance] = mapped_column(
        Enum(FactorImportance, name="factor_importance"),
        default=FactorImportance.normal,
        nullable=False,
    )
