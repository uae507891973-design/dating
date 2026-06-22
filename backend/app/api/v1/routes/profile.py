"""Анкета пользователя: профиль и фото."""

import uuid
from datetime import UTC, date, datetime

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models import Photo, Profile, User
from app.schemas.profile import PhotoOut, ProfileIn, ProfileOut
from app.services.analytics import track_event
from app.services.moderation import classify_nsfw, decide
from app.services.storage import save_photo

router = APIRouter(prefix="/profile", tags=["profile"])
settings = get_settings()


def _age(birth: date) -> int:
    today = date.today()
    return today.year - birth.year - (
        (today.month, today.day) < (birth.month, birth.day)
    )


async def _get_or_create_profile(db: AsyncSession, user: User) -> Profile:
    profile = await db.get(Profile, user.id)
    if profile is None:
        profile = Profile(user_id=user.id)
        db.add(profile)
    return profile


@router.get("", response_model=ProfileOut)
async def get_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileOut:
    profile = await db.get(Profile, user.id)
    if profile is None:
        profile = Profile(user_id=user.id)
    out = ProfileOut.model_validate(profile, from_attributes=True)
    out.is_verified = user.is_verified
    return out


@router.put("", response_model=ProfileOut)
async def update_profile(
    data: ProfileIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileOut:
    if data.birth_date is not None and _age(data.birth_date) < settings.min_user_age:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"minimum age is {settings.min_user_age}",
        )

    profile = await _get_or_create_profile(db, user)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)
    track_event("profile_completed", {"user_id": str(user.id)})
    out = ProfileOut.model_validate(profile, from_attributes=True)
    out.is_verified = user.is_verified
    return out


@router.post("/photos", response_model=PhotoOut, status_code=201)
async def upload_photo(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PhotoOut:
    count = len(
        (
            await db.execute(select(Photo.id).where(Photo.user_id == user.id))
        ).all()
    )
    if count >= settings.max_photos_per_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="photo limit reached"
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="empty file")
    if len(content) > settings.photo_max_bytes:
        raise HTTPException(status_code=400, detail="file too large")

    # Авто-модерация (NSFW) до публикации.
    score = classify_nsfw(content, file.filename or "")
    moderation_status, reason = decide(score)

    url = save_photo(user.id, file.filename or "photo.jpg", content)
    photo = Photo(
        user_id=user.id,
        url=url,
        is_primary=(count == 0),
        moderation_status=moderation_status,
        nsfw_score=score,
        moderation_reason=reason,
        moderated_at=datetime.now(UTC) if reason is not None else None,
    )
    db.add(photo)
    await db.commit()
    await db.refresh(photo)

    track_event(
        "photo_uploaded",
        {"user_id": str(user.id), "status": moderation_status.value},
    )
    return PhotoOut.model_validate(photo, from_attributes=True)


@router.get("/photos", response_model=list[PhotoOut])
async def list_photos(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PhotoOut]:
    photos = (
        await db.execute(select(Photo).where(Photo.user_id == user.id))
    ).scalars().all()
    return [PhotoOut.model_validate(p, from_attributes=True) for p in photos]


@router.delete("/photos/{photo_id}", status_code=204)
async def delete_photo(
    photo_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    photo = await db.get(Photo, photo_id)
    if photo is None or photo.user_id != user.id:
        raise HTTPException(status_code=404, detail="photo not found")
    await db.delete(photo)
    await db.commit()
