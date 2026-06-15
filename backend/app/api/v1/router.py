"""Сборка роутера API v1."""

from fastapi import APIRouter

from app.api.v1.routes import auth, consents, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router, prefix="/v1")
api_router.include_router(consents.router, prefix="/v1")
