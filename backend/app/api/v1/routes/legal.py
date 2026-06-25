"""Юридические документы для экрана регистрации."""

from fastapi import APIRouter

from app.schemas.legal import LegalDocOut
from app.services.legal import documents

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
