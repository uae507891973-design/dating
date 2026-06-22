"""Подбор: лента кандидатов, лайки/пропуски, образование мэтча."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Like, Match, User
from app.models.matching import LikeType
from app.schemas.discovery import CandidateOut, LikeIn, LikeResult
from app.services.analytics import track_event
from app.services.discovery import get_candidates, ordered_pair

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.get("", response_model=list[CandidateOut])
async def discover(
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CandidateOut]:
    """Ранжированная по совместимости подборка кандидатов."""
    candidates = await get_candidates(db, user, limit=min(limit, 50))
    return [
        CandidateOut(
            user_id=c.profile.user_id,
            display_name=c.profile.display_name,
            city=c.profile.city,
            bio=c.profile.bio,
            primary_photo_url=c.primary_photo_url,
            is_verified=c.is_verified,
            score=c.compatibility.score,
            common_questions=c.compatibility.common_questions,
        )
        for c in candidates
    ]


async def _record(
    db: AsyncSession, me: User, target_id, like_type: LikeType
) -> None:
    existing = await db.get(Like, (me.id, target_id))
    if existing is None:
        db.add(Like(from_user=me.id, to_user=target_id, type=like_type))
    else:
        existing.type = like_type


@router.post("/like", response_model=LikeResult)
async def like(
    data: LikeIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LikeResult:
    """Лайк кандидата; при взаимности создаётся мэтч."""
    if data.target_user_id == user.id:
        raise HTTPException(status_code=400, detail="cannot like yourself")

    await _record(db, user, data.target_user_id, LikeType.like)
    track_event("like", {"from": str(user.id), "to": str(data.target_user_id)})

    # Взаимность?
    reciprocal = await db.get(Like, (data.target_user_id, user.id))
    matched = reciprocal is not None and reciprocal.type == LikeType.like

    match_id = None
    if matched:
        a, b = ordered_pair(user.id, data.target_user_id)
        existing = (
            await db.execute(
                select(Match).where(Match.user_a == a, Match.user_b == b)
            )
        ).scalar_one_or_none()
        if existing is None:
            match = Match(user_a=a, user_b=b)
            db.add(match)
            await db.flush()
            match_id = match.id
            track_event("match_created", {"user_a": str(a), "user_b": str(b)})
        else:
            match_id = existing.id

    await db.commit()
    return LikeResult(matched=matched, match_id=match_id)


@router.post("/skip", status_code=204)
async def skip(
    data: LikeIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Пропустить кандидата (не показывать снова)."""
    if data.target_user_id == user.id:
        raise HTTPException(status_code=400, detail="cannot skip yourself")
    await _record(db, user, data.target_user_id, LikeType.skip)
    await db.commit()
