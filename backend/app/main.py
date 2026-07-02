"""Точка входа FastAPI-приложения."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.services.analytics import track_event

settings = get_settings()


def validate_prod_settings() -> None:
    """Не дать запустить prod с небезопасной конфигурацией."""
    if not settings.is_prod:
        return
    problems = []
    weak_secret = (
        settings.jwt_secret in ("", "change-me-in-prod")
        or len(settings.jwt_secret) < 32
    )
    if weak_secret:
        problems.append("jwt_secret не задан или слишком короткий (нужно ≥32 символов)")
    if settings.debug:
        problems.append("debug=True недопустим в prod")
    if settings.otp_debug_log:
        problems.append("otp_debug_log=True недопустим в prod")
    if problems:
        raise RuntimeError("Небезопасная prod-конфигурация: " + "; ".join(problems))


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    validate_prod_settings()
    logger = get_logger("app")
    logger.info("starting %s (%s)", settings.app_name, settings.environment)
    track_event("app_started", {"environment": settings.environment})
    yield
    logger.info("shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="Сервис серьёзных знакомств — backend API",
        lifespan=lifespan,
    )
    app.include_router(api_router)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"service": settings.app_name, "version": __version__}

    return app


app = create_app()
