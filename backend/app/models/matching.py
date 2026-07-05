"""Модели подбора: лайки/пропуски и мэтчи."""

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class LikeType(str, enum.Enum):
    like = "like"
    skip = "skip"


class Like(Base, TimestampMixin):
    __tablename__ = "likes"

    from_user: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    to_user: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    type: Mapped[LikeType] = mapped_column(
        Enum(LikeType, name="like_type"), nullable=False
    )


class Match(Base, TimestampMixin):
    """Взаимная симпатия. user_a < user_b (по строковому uuid) для уникальности."""

    __tablename__ = "matches"
    __table_args__ = (
        UniqueConstraint("user_a", "user_b", name="uq_match_pair"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_a: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_b: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Происхождение диалога: mutual — взаимный лайк, direct — сообщение с карточки.
    origin: Mapped[str] = mapped_column(
        String(16), default="mutual", nullable=False
    )
