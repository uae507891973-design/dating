"""Модераторская очередь фото (RBAC: moderator/admin)."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_moderator
from app.db.session import get_db
from app.models import Photo, User
from app.models.photo import ModerationStatus
from app.schemas.profile import ModerationDecisionIn, ModerationPhotoOut
from app.services.analytics import track_event

router = APIRouter(prefix="/moderation", tags=["moderation"])


@router.get("/photos", response_model=list[ModerationPhotoOut])
async def moderation_queue(
    status: ModerationStatus = ModerationStatus.pending,
    _: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
) -> list[ModerationPhotoOut]:
    """Очередь фото по статусу (по умолчанию — ожидающие проверки)."""
    photos = (
        await db.execute(
            select(Photo).where(Photo.moderation_status == status)
        )
    ).scalars().all()
    return [ModerationPhotoOut.model_validate(p, from_attributes=True) for p in photos]


@router.post("/photos/{photo_id}/decision", response_model=ModerationPhotoOut)
async def moderate_photo(
    photo_id: uuid.UUID,
    data: ModerationDecisionIn,
    moderator: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
) -> ModerationPhotoOut:
    """Ручное решение модератора по фото."""
    if data.decision not in (ModerationStatus.approved, ModerationStatus.rejected):
        raise HTTPException(
            status_code=400, detail="decision must be approved/rejected"
        )

    photo = await db.get(Photo, photo_id)
    if photo is None:
        raise HTTPException(status_code=404, detail="photo not found")

    photo.moderation_status = data.decision
    photo.moderation_reason = data.reason
    photo.moderated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(photo)

    track_event(
        "photo_moderated",
        {
            "photo_id": str(photo.id),
            "moderator_id": str(moderator.id),
            "decision": data.decision.value,
        },
    )
    return ModerationPhotoOut.model_validate(photo, from_attributes=True)
