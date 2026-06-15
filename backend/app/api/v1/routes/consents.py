"""Фиксация согласий пользователя (152-ФЗ)."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Consent, User
from app.schemas.consent import ConsentIn, ConsentOut
from app.services.analytics import track_event

router = APIRouter(prefix="/consents", tags=["consents"])


@router.post("", response_model=ConsentOut, status_code=201)
async def accept_consent(
    data: ConsentIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConsentOut:
    """Зафиксировать принятие документа (политика/условия) с версией и временем."""
    consent = Consent(
        user_id=user.id, doc_type=data.doc_type, doc_version=data.doc_version
    )
    db.add(consent)
    await db.commit()
    await db.refresh(consent)
    track_event(
        "consent_accepted",
        {
            "user_id": str(user.id),
            "doc_type": data.doc_type,
            "version": data.doc_version,
        },
    )
    return ConsentOut(
        doc_type=consent.doc_type,
        doc_version=consent.doc_version,
        accepted_at=consent.accepted_at,
    )


@router.get("", response_model=list[ConsentOut])
async def list_consents(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ConsentOut]:
    """Список зафиксированных согласий пользователя."""
    result = await db.execute(
        select(Consent).where(Consent.user_id == user.id)
    )
    return [
        ConsentOut(
            doc_type=c.doc_type,
            doc_version=c.doc_version,
            accepted_at=c.accepted_at,
        )
        for c in result.scalars().all()
    ]
