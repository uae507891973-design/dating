"""Модераторская очередь фото (RBAC: moderator/admin)."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_moderator
from app.db.session import get_db
from app.models import AuditLog, Photo, RiskFlag, User
from app.models.antifraud import FlagStatus
from app.models.photo import ModerationStatus
from app.schemas.antifraud import AssessmentOut, RiskFlagOut
from app.schemas.profile import ModerationDecisionIn, ModerationPhotoOut
from app.schemas.safety import AuditOut
from app.services.analytics import track_event
from app.services.antifraud import evaluate_and_apply
from app.services.audit import write_audit

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
    write_audit(db, moderator.id, "photo_decision", str(photo.id))
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


@router.get("/audit", response_model=list[AuditOut])
async def audit_log(
    limit: int = 50,
    _: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
) -> list[AuditOut]:
    """Последние записи аудита (доступ к ПДн и модерационные решения)."""
    rows = (
        await db.execute(
            select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit)
        )
    ).scalars().all()
    return [AuditOut.model_validate(r, from_attributes=True) for r in rows]


@router.get("/flags", response_model=list[RiskFlagOut])
async def list_flags(
    status: FlagStatus = FlagStatus.open,
    _: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
) -> list[RiskFlagOut]:
    """Очередь авто-флагов антифрода."""
    rows = (
        await db.execute(
            select(RiskFlag)
            .where(RiskFlag.status == status)
            .order_by(desc(RiskFlag.created_at))
        )
    ).scalars().all()
    return [
        RiskFlagOut(
            id=r.id,
            user_id=r.user_id,
            risk_score=r.risk_score,
            reasons=r.reasons,
            status=r.status.value,
        )
        for r in rows
    ]


@router.post("/flags/{flag_id}/resolve", response_model=RiskFlagOut)
async def resolve_flag(
    flag_id: uuid.UUID,
    moderator: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
) -> RiskFlagOut:
    flag = await db.get(RiskFlag, flag_id)
    if flag is None:
        raise HTTPException(status_code=404, detail="flag not found")
    flag.status = FlagStatus.resolved
    write_audit(db, moderator.id, "flag_resolved", str(flag.id))
    await db.commit()
    await db.refresh(flag)
    return RiskFlagOut(
        id=flag.id,
        user_id=flag.user_id,
        risk_score=flag.risk_score,
        reasons=flag.reasons,
        status=flag.status.value,
    )


@router.post("/antifraud/scan/{user_id}", response_model=AssessmentOut)
async def antifraud_scan(
    user_id: uuid.UUID,
    _: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
) -> AssessmentOut:
    """Принудительно пересчитать риск пользователя."""
    target = await db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="user not found")
    assessment = await evaluate_and_apply(db, target)
    return AssessmentOut(
        user_id=user_id,
        risk_score=assessment.risk_score,
        trust_score=target.trust_score,
        reasons=assessment.reasons,
    )
