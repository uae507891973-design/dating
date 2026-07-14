"""Подбор: лента кандидатов, лайки/пропуски, образование мэтча."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
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
from app.models.message import Message
from app.models.notification import NotificationType
from app.models.photo import ModerationStatus
from app.models.preference import FactorImportance
from app.models.user import UserStatus
from app.schemas.discovery import (
    CandidateOut,
    CategoryPreferenceIn,
    CategoryPreferenceOut,
    DirectMessageIn,
    DirectMessageOut,
    LikeIn,
    LikeResult,
)
from app.services.analytics import track_event
from app.services.billing import is_premium
from app.services.blocks import is_blocked_between
from app.services.chat import screen_message
from app.services.compatibility import CATEGORY_LABELS
from app.services.discovery import get_candidates, ordered_pair
from app.services.legal import missing_reconsents
from app.services.notifications import notify
from app.services.ratelimit import RateLimiter, get_rate_limiter

router = APIRouter(prefix="/discovery", tags=["discovery"])
settings = get_settings()


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
    from app.services.personality import ARCHETYPES

    def _personality(c):
        a = ARCHETYPES.get(c.profile.personality_archetype or "")
        if a is None:
            return None
        return {"key": a.key, "title": a.title, "emoji": a.emoji}

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
            is_online=c.is_online,
            video_state=c.video_state,
            personality=_personality(c),
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
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> LikeResult:
    """Лайк кандидата; при взаимности создаётся мэтч."""
    if await limiter.hit(
        f"like:{user.id}", settings.like_rate_max, settings.like_rate_window_sec
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="rate limited"
        )
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


@router.get("/liked-me", response_model=list[CandidateOut])
async def who_liked_me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CandidateOut]:
    """Кто меня лайкнул — премиум-функция."""
    if not await is_premium(db, user.id):
        raise HTTPException(
            status_code=402,
            detail={"error": "premium_required", "feature": "who_liked_me"},
        )

    liker_ids = (
        await db.execute(
            select(Like.from_user).where(
                Like.to_user == user.id, Like.type == LikeType.like
            )
        )
    ).scalars().all()
    if not liker_ids:
        return []

    profiles = (
        await db.execute(
            select(Profile).where(Profile.user_id.in_(liker_ids))
        )
    ).scalars().all()
    from app.models import Photo

    photos = (
        await db.execute(
            select(Photo).where(
                Photo.user_id.in_(liker_ids),
                Photo.is_primary.is_(True),
                Photo.moderation_status == ModerationStatus.approved,
            )
        )
    ).scalars().all()
    photo_by_user = {p.user_id: p.url for p in photos}

    return [
        CandidateOut(
            user_id=p.user_id,
            display_name=p.display_name,
            city=p.city,
            bio=p.bio,
            primary_photo_url=photo_by_user.get(p.user_id),
            is_verified=False,
            score=0,
            common_questions=0,
        )
        for p in profiles
    ]


@router.post("/message", response_model=DirectMessageOut, status_code=201)
async def message_from_card(
    data: DirectMessageIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> DirectMessageOut:
    """Первое сообщение с карточки кандидата (диалог без взаимного лайка)."""
    if await limiter.hit(
        f"msg:{user.id}",
        settings.message_rate_max,
        settings.message_rate_window_sec,
    ):
        raise HTTPException(status_code=429, detail="rate limited")
    if data.target_user_id == user.id:
        raise HTTPException(status_code=400, detail="cannot message yourself")
    if await is_blocked_between(db, user.id, data.target_user_id):
        raise HTTPException(status_code=403, detail="interaction not allowed")

    target = await db.get(User, data.target_user_id)
    if target is None or target.status != UserStatus.active:
        raise HTTPException(status_code=404, detail="user not found")

    ok, reason = screen_message(data.body, user.is_verified)
    if not ok:
        raise HTTPException(status_code=400, detail=reason)

    # Существующий диалог/мэтч или новый direct-диалог.
    a, b = ordered_pair(user.id, data.target_user_id)
    match = (
        await db.execute(
            select(Match).where(Match.user_a == a, Match.user_b == b)
        )
    ).scalar_one_or_none()
    if match is None:
        match = Match(user_a=a, user_b=b, origin="direct")
        db.add(match)
        await db.flush()

    message = Message(match_id=match.id, sender_id=user.id, body=data.body.strip())
    db.add(message)
    await notify(
        db,
        data.target_user_id,
        NotificationType.message,
        {"title": "Новое сообщение", "match_id": str(match.id)},
    )
    await db.commit()
    await db.refresh(message)
    track_event(
        "direct_message_sent",
        {"from": str(user.id), "match_id": str(match.id)},
    )
    return DirectMessageOut(match_id=match.id, message_id=message.id)


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
