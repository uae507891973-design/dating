"""Подбор: лента кандидатов, лайки/пропуски, образование мэтча."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import (
    CategoryPreference,
    Like,
    Match,
    Profile,
    Psychoprofile,
    User,
)
from app.models.matching import LikeType
from app.models.notification import NotificationType
from app.models.preference import FactorImportance
from app.schemas.discovery import (
    CandidateOut,
    CategoryPreferenceIn,
    CategoryPreferenceOut,
    LikeIn,
    LikeResult,
)
from app.services.analytics import track_event
from app.services.blocks import is_blocked_between
from app.services.compatibility import CATEGORY_LABELS
from app.services.discovery import get_candidates, ordered_pair
from app.services.legal import missing_reconsents
from app.services.notifications import notify

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.get("", response_model=list[CandidateOut])
async def discover(
    limit: int = 20,
    max_distance_km: float | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CandidateOut]:
    """Ранжированная по совместимости подборка кандидатов."""
    # Гейт: актуальные согласия (152-ФЗ) при смене версии документов.
    pending = await missing_reconsents(db, user.id)
    if pending:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "reconsent_required", "missing": pending},
        )

    # Гейт: анкета заполнена (пол/кого ищу) и тест пройден (есть психопрофиль).
    profile = await db.get(Profile, user.id)
    psychoprofile = await db.get(Psychoprofile, user.id)
    if (
        profile is None
        or profile.gender is None
        or profile.looking_for is None
        or psychoprofile is None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "profile_incomplete",
                "need": "Заполните анкету (пол, кого ищете) и пройдите тест",
            },
        )

    candidates = await get_candidates(
        db, user, limit=min(limit, 50), max_distance_km=max_distance_km
    )
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
            reasons=c.reasons,
        )
        for c in candidates
    ]


@router.get("/preferences", response_model=list[CategoryPreferenceOut])
async def get_preferences(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CategoryPreferenceOut]:
    """Текущая важность категорий (scrutability)."""
    rows = (
        await db.execute(
            select(CategoryPreference).where(CategoryPreference.user_id == user.id)
        )
    ).scalars().all()
    return [
        CategoryPreferenceOut(category=r.category, importance=r.importance.value)
        for r in rows
    ]


@router.put("/preferences", response_model=list[CategoryPreferenceOut])
async def set_preferences(
    prefs: list[CategoryPreferenceIn],
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CategoryPreferenceOut]:
    """Задать важность факторов — влияет на ранжирование подбора."""
    for p in prefs:
        if p.category not in CATEGORY_LABELS:
            raise HTTPException(
                status_code=400, detail=f"unknown category: {p.category}"
            )
        try:
            importance = FactorImportance(p.importance)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail="invalid importance"
            ) from exc

        existing = await db.get(CategoryPreference, (user.id, p.category))
        if existing is None:
            db.add(
                CategoryPreference(
                    user_id=user.id, category=p.category, importance=importance
                )
            )
        else:
            existing.importance = importance

    await db.commit()
    track_event("preferences_updated", {"user_id": str(user.id)})
    return await get_preferences(user, db)


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
    if await is_blocked_between(db, user.id, data.target_user_id):
        raise HTTPException(status_code=403, detail="interaction not allowed")

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
            payload = {"title": "Новый мэтч!", "match_id": str(match_id)}
            await notify(db, a, NotificationType.match, payload)
            await notify(db, b, NotificationType.match, payload)
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
