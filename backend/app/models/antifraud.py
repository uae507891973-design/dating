"""Модель риск-флага антифрода."""

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin


class FlagStatus(str, enum.Enum):
    open = "open"
    resolved = "resolved"


class RiskFlag(Base, TimestampMixin):
    """Авто-флаг подозрительного поведения для модераторской очереди."""

    __tablename__ = "risk_flags"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    reasons: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[FlagStatus] = mapped_column(
        Enum(FlagStatus, name="flag_status"),
        default=FlagStatus.open,
        nullable=False,
        index=True,
    )
