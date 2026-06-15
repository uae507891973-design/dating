"""Healthcheck-эндпоинты."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness: приложение отвечает."""
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=__version__,
        environment=settings.environment,
    )


@router.get("/health/db", response_model=HealthResponse)
async def health_db(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """Readiness: доступна БД."""
    await db.execute(text("SELECT 1"))
    return HealthResponse(
        status="ok",
        service=f"{settings.app_name}:db",
        version=__version__,
        environment=settings.environment,
    )
