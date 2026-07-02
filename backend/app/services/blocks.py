"""Проверка блокировок между пользователями (в обе стороны)."""

import uuid

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Block


async def is_blocked_between(
    db: AsyncSession, a: uuid.UUID, b: uuid.UUID
) -> bool:
    """True, если есть блокировка a→b или b→a."""
    row = (
        await db.execute(
            select(Block.blocker_id).where(
                or_(
                    and_(Block.blocker_id == a, Block.blocked_id == b),
                    and_(Block.blocker_id == b, Block.blocked_id == a),
                )
            ).limit(1)
        )
    ).first()
    return row is not None
