"""Верификация профиля: селфи + документ → проверка модерацией.

Файлы не публикуются: хранятся приватно и используются только для проверки.
"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models import User, Verification
from app.models.safety import VerificationStatus
from app.schemas.safety import VerificationOut
from app.services.analytics import track_event
from app.services.audit import write_audit
from app.services.storage import detect_image_ext
from app.services.verification import check_selfie, save_private

router = APIRouter(prefix="/verify", tags=["verify"])
settings = get_settings()


async def _current_verification(
    db: AsyncSession, user: User
) -> Verification | None:
    return (
        await db.execute(
            select(Verification)
            .where(Verification.user_id == user.id)
            .order_by(desc(Verification.created_at))
            .limit(1)
        )
    ).scalar_one_or_none()


def _out(v: Verification | None, user: User) -> VerificationOut:
    if v is None:
        return VerificationOut(status=None, is_verified=user.is_verified)
    return VerificationOut(
        status=v.status,
        is_verified=user.is_verified,
        selfie_uploaded=v.selfie_path is not None,
        document_uploaded=v.document_path is not None,
        submitted=v.selfie_path is not None and v.document_path is not None,
    )


async def _get_or_create_draft(db: AsyncSession, user: User) -> Verification:
    v = await _current_verification(db, user)
    # Новая заявка, если прошлая уже решена.
    if v is None or v.status != VerificationStatus.pending:
        v = Verification(user_id=user.id, type="identity")
        db.add(v)
        await db.flush()
    return v


async def _read_image(file: UploadFile) -> tuple[bytes, str]:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="empty file")
    if len(content) > settings.photo_max_bytes:
        raise HTTPException(status_code=400, detail="file too large")
    ext = detect_image_ext(content)
    if ext is None:
        raise HTTPException(status_code=400, detail="unsupported image format")
    return content, ext


@router.post("/selfie", response_model=VerificationOut)
async def upload_selfie(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VerificationOut:
    """Шаг 1: селфи (предварительная liveness-проверка)."""
    content, ext = await _read_image(file)
    if not check_selfie(content, file.filename or ""):
        raise HTTPException(
            status_code=400,
            detail="liveness check failed, retake the selfie",
        )

    v = await _get_or_create_draft(db, user)
    v.selfie_path = save_private(user.id, "selfie", content, ext)
    submitted = v.document_path is not None
    write_audit(db, user.id, "verification_selfie_uploaded", str(v.id))
    if submitted:
        write_audit(db, user.id, "verification_submitted", str(v.id))
        track_event("verification_submitted", {"user_id": str(user.id)})
    await db.commit()
    await db.refresh(v)
    return _out(v, user)


@router.post("/document", response_model=VerificationOut)
async def upload_document(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VerificationOut:
    """Шаг 2: фото документа (используется только для проверки)."""
    content, ext = await _read_image(file)

    v = await _get_or_create_draft(db, user)
    v.document_path = save_private(user.id, "document", content, ext)
    submitted = v.selfie_path is not None
    write_audit(db, user.id, "verification_document_uploaded", str(v.id))
    if submitted:
        write_audit(db, user.id, "verification_submitted", str(v.id))
        track_event("verification_submitted", {"user_id": str(user.id)})
    await db.commit()
    await db.refresh(v)
    return _out(v, user)


@router.get("/status", response_model=VerificationOut)
async def verify_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VerificationOut:
    v = await _current_verification(db, user)
    return _out(v, user)
