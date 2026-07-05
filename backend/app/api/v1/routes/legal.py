"""Юридические документы: список, тексты, переподтверждение."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Consent, User
from app.schemas.legal import LegalDocOut, ReconsentIn
from app.services.analytics import track_event
from app.services.legal import (
    document_text,
    documents,
    missing_reconsents,
    version_for,
)

router = APIRouter(prefix="/legal", tags=["legal"])


@router.get("/documents", response_model=list[LegalDocOut])
async def list_documents() -> list[LegalDocOut]:
    """Документы и версии, которые показываются галочками при регистрации."""
    return [
        LegalDocOut(
            type=d.type,
            version=d.version,
            title=d.title,
            url=d.url,
            required=d.required,
        )
        for d in documents()
    ]


@router.get("/documents/{doc_type}", response_model=dict)
async def get_document(doc_type: str) -> dict:
    """Текст конкретного документа (политика/оферта/рассылки)."""
    text = document_text(doc_type)
    if text is None:
        raise HTTPException(status_code=404, detail="document not found")
    return {"type": doc_type, "version": version_for(doc_type), "text": text}


@router.get("/pending", response_model=list[str])
async def pending_reconsents(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    """Обязательные документы, требующие (пере)подтверждения текущей версии."""
    return await missing_reconsents(db, user.id)


@router.post("/reconsent", response_model=list[str])
async def reconsent(
    data: ReconsentIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    """Принять актуальные версии документов; вернуть оставшиеся непринятые."""
    for doc_type in set(data.accepted_documents):
        version = version_for(doc_type)
        if version is not None:
            db.add(
                Consent(user_id=user.id, doc_type=doc_type, doc_version=version)
            )
    await db.commit()
    track_event("reconsent", {"user_id": str(user.id)})
    return await missing_reconsents(db, user.id)
