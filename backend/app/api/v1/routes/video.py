"""Видеознакомство «вслепую»: сессии, блюр, согласие на продолжение.

Реализует логику состояний и согласий поверх будущего RTC-провайдера РФ.
Сам медиапоток (WebRTC) подключается через сигналинг отдельно; здесь —
жизненный цикл, безопасность и связка с trust-score.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models import Match, Profile, User, VideoSession
from app.models.notification import NotificationType
from app.models.video import VideoStatus
from app.schemas.video import BlurIn, ContinueIn, VideoSessionOut
from app.services.analytics import track_event
from app.services.audit import write_audit
from app.services.blocks import is_blocked_between
from app.services.notifications import notify
from app.services.presence import video_state

router = APIRouter(tags=["video"])
settings = get_settings()


async def _match_for_user(
    db: AsyncSession, match_id: uuid.UUID, user: User
) -> tuple[Match, uuid.UUID]:
    match = await db.get(Match, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="match not found")
    if user.id not in (match.user_a, match.user_b):
        raise HTTPException(status_code=403, detail="not a participant")
    other = match.user_b if match.user_a == user.id else match.user_a
    return match, other


def _age_sec(dt: datetime) -> float:
    now = datetime.now(UTC)
    ref = dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
    return (now - ref).total_seconds()


async def _apply_expiry(db: AsyncSession, session: VideoSession) -> None:
    """Авто-истечение зависших сессий (не принят вовремя / слишком долгий звонок)."""
    changed = False
    if (
        session.status == VideoStatus.requested
        and _age_sec(session.created_at) > settings.video_request_ttl_sec
    ):
        session.status = VideoStatus.declined
        session.ended_at = datetime.now(UTC)
        changed = True
    elif (
        session.status == VideoStatus.active
        and session.started_at is not None
        and _age_sec(session.started_at) > settings.video_max_active_sec
    ):
        session.status = VideoStatus.ended
        session.ended_at = datetime.now(UTC)
        changed = True
    if changed:
        await db.commit()


async def _session_for_user(
    db: AsyncSession, session_id: uuid.UUID, user: User
) -> tuple[VideoSession, Match]:
    session = await db.get(VideoSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    match, _ = await _match_for_user(db, session.match_id, user)
    await _apply_expiry(db, session)
    return session, match


@router.post(
    "/matches/{match_id}/video", response_model=VideoSessionOut, status_code=201
)
async def initiate_video(
    match_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VideoSessionOut:
    """Инициировать блюр-видеозвонок по мэтчу."""
    _, other_id = await _match_for_user(db, match_id, user)
    if await is_blocked_between(db, user.id, other_id):
        raise HTTPException(status_code=403, detail="interaction not allowed")

    # Видеозвонок возможен, только если получатель онлайн и не запретил звонки.
    other_user = await db.get(User, other_id)
    other_profile = await db.get(Profile, other_id)
    state = video_state(other_profile, other_user)
    if state != "available":
        raise HTTPException(
            status_code=409,
            detail={"error": "video_unavailable", "reason": state},
        )

    active = (
        await db.execute(
            select(VideoSession).where(
                VideoSession.match_id == match_id,
                VideoSession.status.in_(
                    [VideoStatus.requested, VideoStatus.active]
                ),
            )
        )
    ).scalar_one_or_none()
    if active is not None:
        raise HTTPException(status_code=409, detail="active session already exists")

    session = VideoSession(
        match_id=match_id,
        initiator_id=user.id,
        blur_level=settings.video_default_blur,
    )
    db.add(session)
    await notify(
        db,
        other_id,
        NotificationType.video_call,
        {"title": "Входящий видеозвонок", "match_id": str(match_id)},
    )
    await db.commit()
    await db.refresh(session)
    track_event("video_call_started", {"match_id": str(match_id)})
    return VideoSessionOut.model_validate(session, from_attributes=True)


@router.post("/video/{session_id}/accept", response_model=VideoSessionOut)
async def accept_video(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VideoSessionOut:
    """Партнёр принимает звонок (звонок становится активным)."""
    session, _ = await _session_for_user(db, session_id, user)
    if user.id == session.initiator_id:
        raise HTTPException(status_code=400, detail="initiator cannot accept")
    if session.status != VideoStatus.requested:
        raise HTTPException(status_code=400, detail="session not joinable")
    session.status = VideoStatus.active
    session.started_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(session)
    return VideoSessionOut.model_validate(session, from_attributes=True)


@router.post("/video/{session_id}/decline", response_model=VideoSessionOut)
async def decline_video(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VideoSessionOut:
    session, _ = await _session_for_user(db, session_id, user)
    if session.status not in (VideoStatus.requested, VideoStatus.active):
        raise HTTPException(status_code=400, detail="session already finished")
    session.status = VideoStatus.declined
    session.ended_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(session)
    return VideoSessionOut.model_validate(session, from_attributes=True)


@router.post("/video/{session_id}/blur", response_model=VideoSessionOut)
async def set_blur(
    session_id: uuid.UUID,
    data: BlurIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VideoSessionOut:
    """Управление уровнем блюра во время звонка."""
    session, _ = await _session_for_user(db, session_id, user)
    if session.status != VideoStatus.active:
        raise HTTPException(status_code=400, detail="session not active")
    session.blur_level = data.level
    await db.commit()
    await db.refresh(session)
    return VideoSessionOut.model_validate(session, from_attributes=True)


@router.post("/video/{session_id}/continue", response_model=VideoSessionOut)
async def vote_continue(
    session_id: uuid.UUID,
    data: ContinueIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VideoSessionOut:
    """Голос за продолжение/раскрытие. При обоюдном «да» блюр снимается."""
    session, _ = await _session_for_user(db, session_id, user)
    if session.status != VideoStatus.active:
        raise HTTPException(status_code=400, detail="session not active")

    if user.id == session.initiator_id:
        session.continue_initiator = data.yes
    else:
        session.continue_partner = data.yes

    if session.continue_initiator and session.continue_partner:
        session.revealed = True
        session.blur_level = 0.0
        track_event("video_continue_yes", {"session_id": str(session.id)})

    await db.commit()
    await db.refresh(session)
    return VideoSessionOut.model_validate(session, from_attributes=True)


@router.post("/video/{session_id}/end", response_model=VideoSessionOut)
async def end_video(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VideoSessionOut:
    """Завершить звонок. Живой видеоконтакт повышает trust-score обоих."""
    session, match = await _session_for_user(db, session_id, user)
    was_active = session.status == VideoStatus.active
    if session.status in (VideoStatus.ended, VideoStatus.declined):
        raise HTTPException(status_code=400, detail="session already finished")

    session.status = VideoStatus.ended
    session.ended_at = datetime.now(UTC)

    if was_active:
        # Сигнал «живой человек» — бонус к trust-score участникам.
        for uid in (match.user_a, match.user_b):
            participant = await db.get(User, uid)
            if participant is not None:
                participant.trust_score = min(
                    100, participant.trust_score + settings.video_trust_bonus
                )
        write_audit(db, user.id, "video_completed", str(session.id))
        track_event("video_call_completed", {"session_id": str(session.id)})

    await db.commit()
    await db.refresh(session)
    return VideoSessionOut.model_validate(session, from_attributes=True)


@router.get("/video/{session_id}", response_model=VideoSessionOut)
async def get_video(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VideoSessionOut:
    session, _ = await _session_for_user(db, session_id, user)
    return VideoSessionOut.model_validate(session, from_attributes=True)
