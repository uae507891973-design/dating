"""JWT: выпуск и проверка access/refresh токенов."""

from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import get_settings

settings = get_settings()


class TokenError(Exception):
    """Невалидный или просроченный токен."""


def _create_token(subject: str, token_type: str, expires: timedelta) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str) -> str:
    return _create_token(
        subject, "access", timedelta(minutes=settings.jwt_access_ttl_min)
    )


def create_refresh_token(subject: str) -> str:
    return _create_token(
        subject, "refresh", timedelta(days=settings.jwt_refresh_ttl_days)
    )


def decode_token(token: str, expected_type: str) -> str:
    """Вернуть subject (user_id) или возбудить TokenError."""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError as exc:  # noqa: BLE001
        raise TokenError("invalid token") from exc

    if payload.get("type") != expected_type:
        raise TokenError("wrong token type")
    subject = payload.get("sub")
    if not subject:
        raise TokenError("missing subject")
    return subject
