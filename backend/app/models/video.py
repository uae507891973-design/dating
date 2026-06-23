"""Модель сессии видеознакомства «вслепую»."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class VideoStatus(str, enum.Enum):
    requested = "requested"  # инициирован, ждёт принятия
    active = "active"        # идёт звонок
    ended = "ended"
    declined = "declined"


class VideoSession(Base, TimestampMixin):
    __tablename__ = "video_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    match_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("matches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    initiator_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[VideoStatus] = mapped_column(
        Enum(VideoStatus, name="video_status"),
        default=VideoStatus.requested,
        nullable=False,
    )
    # Блюр: 1.0 — максимальное размытие, 0.0 — открыто.
    blur_level: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    # Голоса «продолжить/раскрыть» по ролям.
    continue_initiator: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    continue_partner: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    revealed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
