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
from app.models import Match, User, VideoSession
from app.models.video import VideoStatus
from app.schemas.video import BlurIn, ContinueIn, VideoSessionOut
from app.services.analytics import track_event
from app.services.audit import write_audit

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


async def _session_for_user(
    db: AsyncSession, session_id: uuid.UUID, user: User
) -> tuple[VideoSession, Match]:
    session = await db.get(VideoSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    match, _ = await _match_for_user(db, session.match_id, user)
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
    await _match_for_user(db, match_id, user)

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
