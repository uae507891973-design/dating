"""Движок подбора: кандидатогенерация (фильтры) + ранжирование (совместимость)."""

import uuid
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Block, Like, Photo, Profile, PsychotestAnswer, User
from app.models.photo import ModerationStatus
from app.models.user import UserStatus
from app.services.compatibility import (
    AnswerMap,
    CompatibilityResult,
    compute_compatibility,
)


@dataclass
class Candidate:
    profile: Profile
    primary_photo_url: str | None
    is_verified: bool
    compatibility: CompatibilityResult


async def load_answers(db: AsyncSession, user_id: uuid.UUID) -> AnswerMap:
    """Ответы пользователя в формате для функции совместимости."""
    rows = (
        await db.execute(
            select(PsychotestAnswer).where(PsychotestAnswer.user_id == user_id)
        )
    ).scalars().all()
    return {r.question_id: (r.value, r.importance) for r in rows}


async def _excluded_ids(db: AsyncSession, me: uuid.UUID) -> set[uuid.UUID]:
    """Сам пользователь + уже оценённые + заблокированные (в обе стороны)."""
    excluded: set[uuid.UUID] = {me}

    liked = (
        await db.execute(select(Like.to_user).where(Like.from_user == me))
    ).scalars().all()
    excluded.update(liked)

    blocks = (
        await db.execute(
            select(Block).where(
                or_(Block.blocker_id == me, Block.blocked_id == me)
            )
        )
    ).scalars().all()
    for b in blocks:
        excluded.add(b.blocker_id)
        excluded.add(b.blocked_id)

    return excluded


async def get_candidates(
    db: AsyncSession, me: User, limit: int = 20
) -> list[Candidate]:
    """Сформировать ранжированную по совместимости подборку."""
    my_profile = await db.get(Profile, me.id)
    excluded = await _excluded_ids(db, me.id)

    stmt = (
        select(Profile)
        .join(User, User.id == Profile.user_id)
        .where(User.status == UserStatus.active)
        .where(Profile.user_id.notin_(excluded))
    )
    # Взаимная ориентация по полу (если заданы предпочтения).
    if my_profile and my_profile.looking_for is not None:
        stmt = stmt.where(Profile.gender == my_profile.looking_for)
    if my_profile and my_profile.gender is not None:
        stmt = stmt.where(
            or_(
                Profile.looking_for == my_profile.gender,
                Profile.looking_for.is_(None),
            )
        )

    candidate_profiles = (await db.execute(stmt)).scalars().all()
    if not candidate_profiles:
        return []

    my_answers = await load_answers(db, me.id)

    # Основные одобренные фото кандидатов одним запросом.
    cand_ids = [p.user_id for p in candidate_profiles]
    photos = (
        await db.execute(
            select(Photo).where(
                Photo.user_id.in_(cand_ids),
                Photo.moderation_status == ModerationStatus.approved,
                Photo.is_primary.is_(True),
            )
        )
    ).scalars().all()
    photo_by_user = {p.user_id: p.url for p in photos}

    # Верификация кандидатов.
    users = (
        await db.execute(select(User).where(User.id.in_(cand_ids)))
    ).scalars().all()
    verified_by_user = {u.id: u.is_verified for u in users}

    results: list[Candidate] = []
    for profile in candidate_profiles:
        their_answers = await load_answers(db, profile.user_id)
        compat = compute_compatibility(my_answers, their_answers)
        results.append(
            Candidate(
                profile=profile,
                primary_photo_url=photo_by_user.get(profile.user_id),
                is_verified=verified_by_user.get(profile.user_id, False),
                compatibility=compat,
            )
        )

    # Ранжирование: по убыванию совместимости.
    results.sort(key=lambda c: c.compatibility.score, reverse=True)
    return results[:limit]


def ordered_pair(a: uuid.UUID, b: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    """Упорядоченная пара для уникальности мэтча."""
    return (a, b) if str(a) < str(b) else (b, a)
