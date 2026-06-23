"""Сборка роутера API v1."""

from fastapi import APIRouter

from app.api.v1.routes import (
    auth,
    chat,
    consents,
    discovery,
    health,
    moderation,
    onboarding,
    profile,
    safety,
    verify,
    video,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router, prefix="/v1")
api_router.include_router(consents.router, prefix="/v1")
api_router.include_router(onboarding.router, prefix="/v1")
api_router.include_router(profile.router, prefix="/v1")
api_router.include_router(verify.router, prefix="/v1")
api_router.include_router(safety.router, prefix="/v1")
api_router.include_router(discovery.router, prefix="/v1")
api_router.include_router(chat.router, prefix="/v1")
api_router.include_router(video.router, prefix="/v1")
api_router.include_router(moderation.router, prefix="/v1")
