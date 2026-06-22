"""Аудит-лог: фиксация доступа к ПДн и значимых действий (152-ФЗ)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


def write_audit(
    db: AsyncSession,
    actor_id: uuid.UUID | None,
    action: str,
    target: str | None = None,
) -> None:
    """Добавить запись аудита в текущую сессию (commit — на стороне вызывающего)."""
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            target=target,
            created_at=datetime.now(UTC),
        )
    )
