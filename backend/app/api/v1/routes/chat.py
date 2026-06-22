"""Чат: мэтчи, сообщения, айсбрейкеры, real-time WebSocket."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import asc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.security import TokenError, decode_token
from app.db.session import SessionLocal, get_db
from app.models import Match, Message, Photo, Profile, User
from app.models.message import MessageStatus
from app.models.photo import ModerationStatus
from app.schemas.chat import IcebreakersOut, MatchOut, MessageIn, MessageOut
from app.services.analytics import track_event
from app.services.antifraud import evaluate_and_apply
from app.services.chat import generate_icebreakers, manager, screen_message
from app.services.compatibility import compute_compatibility
from app.services.discovery import load_answers

router = APIRouter(tags=["chat"])


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


@router.get("/matches", response_model=list[MatchOut])
async def list_matches(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MatchOut]:
    matches = (
        await db.execute(
            select(Match).where(
                or_(Match.user_a == user.id, Match.user_b == user.id)
            )
        )
    ).scalars().all()

    result: list[MatchOut] = []
    for m in matches:
        other_id = m.user_b if m.user_a == user.id else m.user_a
        profile = await db.get(Profile, other_id)
        other_user = await db.get(User, other_id)
        photo = (
            await db.execute(
                select(Photo.url).where(
                    Photo.user_id == other_id,
                    Photo.is_primary.is_(True),
                    Photo.moderation_status == ModerationStatus.approved,
                )
            )
        ).scalar_one_or_none()
        result.append(
            MatchOut(
                match_id=m.id,
                other_user_id=other_id,
                other_display_name=profile.display_name if profile else None,
                other_photo_url=photo,
                other_is_verified=other_user.is_verified if other_user else False,
                created_at=m.created_at,
            )
        )
    return result


@router.get("/matches/{match_id}/messages", response_model=list[MessageOut])
async def get_messages(
    match_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MessageOut]:
    await _match_for_user(db, match_id, user)
    rows = (
        await db.execute(
            select(Message)
            .where(Message.match_id == match_id)
            .order_by(asc(Message.created_at))
        )
    ).scalars().all()
    return [MessageOut.model_validate(m, from_attributes=True) for m in rows]


@router.post("/matches/{match_id}/messages", response_model=MessageOut, status_code=201)
async def send_message(
    match_id: uuid.UUID,
    data: MessageIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageOut:
    await _match_for_user(db, match_id, user)

    ok, reason = screen_message(data.body, user.is_verified)
    if not ok:
        raise HTTPException(status_code=400, detail=reason)

    message = Message(match_id=match_id, sender_id=user.id, body=data.body.strip())
    db.add(message)
    await db.commit()
    await db.refresh(message)

    out = MessageOut.model_validate(message, from_attributes=True)
    await manager.broadcast(match_id, out.model_dump(mode="json"))
    track_event("message_sent", {"match_id": str(match_id), "sender": str(user.id)})

    # Антифрод-оценка по поведению (обновляет trust-score, при риске — флаг).
    await evaluate_and_apply(db, user)
    return out


@router.post("/matches/{match_id}/read", status_code=204)
async def mark_read(
    match_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Отметить сообщения собеседника как прочитанные."""
    await _match_for_user(db, match_id, user)
    rows = (
        await db.execute(
            select(Message).where(
                Message.match_id == match_id,
                Message.sender_id != user.id,
                Message.status == MessageStatus.sent,
            )
        )
    ).scalars().all()
    for m in rows:
        m.status = MessageStatus.read
    await db.commit()


@router.get("/matches/{match_id}/icebreakers", response_model=IcebreakersOut)
async def icebreakers(
    match_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IcebreakersOut:
    _, other_id = await _match_for_user(db, match_id, user)
    my_answers = await load_answers(db, user.id)
    their_answers = await load_answers(db, other_id)
    compat = compute_compatibility(my_answers, their_answers)
    other_profile = await db.get(Profile, other_id)
    name = other_profile.display_name if other_profile else None
    return IcebreakersOut(
        suggestions=generate_icebreakers(compat.category_contributions, name)
    )


@router.websocket("/ws/chat/{match_id}")
async def chat_ws(websocket: WebSocket, match_id: uuid.UUID, token: str = "") -> None:
    """Real-time канал чата. Авторизация через query-параметр token."""
    try:
        subject = decode_token(token, expected_type="access")
        user_id = uuid.UUID(subject)
    except (TokenError, ValueError):
        await websocket.close(code=4401)
        return

    # Проверка членства в мэтче.
    async with SessionLocal() as db:
        match = await db.get(Match, match_id)
        if match is None or user_id not in (match.user_a, match.user_b):
            await websocket.close(code=4403)
            return
        user = await db.get(User, user_id)

    await manager.connect(match_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            body = (data or {}).get("body", "")
            ok, _ = screen_message(body, user.is_verified if user else False)
            if not ok:
                await websocket.send_json({"error": "message rejected"})
                continue
            async with SessionLocal() as db:
                message = Message(
                    match_id=match_id, sender_id=user_id, body=body.strip()
                )
                db.add(message)
                await db.commit()
                await db.refresh(message)
                out = MessageOut.model_validate(message, from_attributes=True)
            await manager.broadcast(match_id, out.model_dump(mode="json"))
    except WebSocketDisconnect:
        manager.disconnect(match_id, websocket)
