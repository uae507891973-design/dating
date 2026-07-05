"""Модель пользователя."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.crypto import EncryptedStr
from app.db.base import Base, TimestampMixin


class UserStatus(str, enum.Enum):
    pending = "pending"      # зарегистрирован, онбординг не завершён
    active = "active"
    blocked = "blocked"
    deleted = "deleted"


class UserRole(str, enum.Enum):
    user = "user"
    moderator = "moderator"
    admin = "admin"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # PII шифруется в покое (AES-SIV, детерминированно — поиск/уникальность работают).
    phone: Mapped[str | None] = mapped_column(
        EncryptedStr(255), unique=True, index=True, nullable=True
    )
    email: Mapped[str | None] = mapped_column(
        EncryptedStr(512), unique=True, index=True, nullable=True
    )

    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status"),
        default=UserStatus.pending,
        nullable=False,
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"),
        default=UserRole.user,
        nullable=False,
    )
    last_active_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    # Внутренний показатель доверия 0..100 (НЕ публичная шкала). Чем ниже — рискованнее.
    trust_score: Mapped[int] = mapped_column(
        Integer, default=100, nullable=False
    )
    # Версия токенов: инкремент при logout/сбросе инвалидирует все выданные токены.
    token_version: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )

    profile: Mapped["Profile"] = relationship(  # noqa: F821
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    consents: Mapped[list["Consent"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
