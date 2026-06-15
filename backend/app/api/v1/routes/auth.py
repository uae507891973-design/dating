"""Аутентификация по SMS-OTP с выдачей JWT."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.db.session import get_db
from app.models import User
from app.models.user import UserStatus
from app.schemas.auth import (
    RefreshIn,
    RequestOtpIn,
    RequestOtpOut,
    TokenPair,
    VerifyOtpIn,
)
from app.services.analytics import track_event
from app.services.otp import OTPStore, generate_code, get_otp_store, send_sms

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.post("/request-otp", response_model=RequestOtpOut)
async def request_otp(
    data: RequestOtpIn,
    store: OTPStore = Depends(get_otp_store),
) -> RequestOtpOut:
    """Сгенерировать и отправить SMS-код (с лимитом запросов)."""
    requests = await store.incr_requests(data.phone, settings.otp_request_window_sec)
    if requests > settings.otp_request_max:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many otp requests",
        )

    code = generate_code(settings.otp_length)
    await store.set_code(data.phone, code, settings.otp_ttl_sec)
    send_sms(data.phone, code)
    track_event("otp_requested", {"phone": data.phone})
    return RequestOtpOut(sent=True, retry_after_sec=settings.otp_ttl_sec)


@router.post("/verify-otp", response_model=TokenPair)
async def verify_otp(
    data: VerifyOtpIn,
    db: AsyncSession = Depends(get_db),
    store: OTPStore = Depends(get_otp_store),
) -> TokenPair:
    """Проверить код, создать/найти пользователя и выдать токены."""
    attempts = await store.incr_attempts(data.phone, settings.otp_ttl_sec)
    if attempts > settings.otp_max_attempts:
        await store.delete_code(data.phone)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many attempts",
        )

    stored = await store.get_code(data.phone)
    if stored is None or stored != data.code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid or expired code"
        )

    await store.delete_code(data.phone)

    result = await db.execute(select(User).where(User.phone == data.phone))
    user = result.scalar_one_or_none()
    is_new_user = user is None
    if user is None:
        user = User(phone=data.phone, status=UserStatus.pending)
        db.add(user)
        await db.flush()
        track_event("registration_completed", {"user_id": str(user.id)})

    user.last_active_at = datetime.now(UTC)
    await db.commit()

    track_event(
        "login", {"user_id": str(user.id), "is_new_user": is_new_user}
    )
    return TokenPair(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
        is_new_user=is_new_user,
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(data: RefreshIn) -> TokenPair:
    """Обновить пару токенов по refresh-токену."""
    try:
        subject = decode_token(data.refresh_token, expected_type="refresh")
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid refresh token"
        ) from exc
    return TokenPair(
        access_token=create_access_token(subject),
        refresh_token=create_refresh_token(subject),
    )
