"""Модель анкеты пользователя."""

import enum
import uuid
from datetime import date

from sqlalchemy import Date, Enum, Float, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Gender(str, enum.Enum):
    male = "male"
    female = "female"


class Intent(str, enum.Enum):
    """Намерение пользователя (используется мэтчингом)."""

    marriage = "marriage"
    relationship = "relationship"
    friendship = "friendship"


class Profile(Base, TimestampMixin):
    __tablename__ = "profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    display_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[Gender | None] = mapped_column(
        Enum(Gender, name="gender"), nullable=True
    )
    looking_for: Mapped[Gender | None] = mapped_column(
        Enum(Gender, name="looking_for"), nullable=True
    )
    intent: Mapped[Intent | None] = mapped_column(
        Enum(Intent, name="intent"), nullable=True
    )
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Гео: на фундаменте — координаты; миграция на PostGIS geography(Point) — Стадия 2
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="profile")  # noqa: F821
