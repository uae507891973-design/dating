"""Селфи-верификация и бейдж Verified."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User, Verification
from app.models.safety import VerificationStatus
from app.schemas.safety import VerificationOut
from app.services.analytics import track_event
from app.services.audit import write_audit
from app.services.verification import check_selfie

router = APIRouter(prefix="/verify", tags=["verify"])


@router.post("/selfie", response_model=VerificationOut)
async def verify_selfie(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VerificationOut:
    """Загрузить селфи для верификации (liveness + сверка — заглушка)."""
    content = await file.read()
    passed = check_selfie(content, file.filename or "")
    result = (
        VerificationStatus.approved if passed else VerificationStatus.rejected
    )

    db.add(
        Verification(
            user_id=user.id,
            type="selfie",
            status=result,
            decided_at=datetime.now(UTC),
        )
    )
    if passed:
        user.is_verified = True

    write_audit(db, user.id, "verification_selfie", result.value)
    await db.commit()

    track_event(
        "verification_completed",
        {"user_id": str(user.id), "status": result.value},
    )
    return VerificationOut(status=result, is_verified=user.is_verified)


@router.get("/status", response_model=VerificationOut)
async def verify_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VerificationOut:
    last = (
        await db.execute(
            select(Verification)
            .where(Verification.user_id == user.id)
            .order_by(desc(Verification.created_at))
            .limit(1)
        )
    ).scalar_one_or_none()
    status_value = last.status if last else VerificationStatus.pending
    return VerificationOut(status=status_value, is_verified=user.is_verified)
