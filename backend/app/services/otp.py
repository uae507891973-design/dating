"""OTP-сервис: генерация, хранение и проверка SMS-кодов с лимитами.

Два бэкенда хранилища:
- RedisOTPStore — продакшн (TTL и счётчики в Redis);
- MemoryOTPStore — для тестов/локальной разработки без Redis.

Отправка SMS на фундаменте — заглушка (код пишется в лог). Реальный
SMS-провайдер РФ подключается через интерфейс SmsSender без изменения логики.
"""

import secrets
import time
from abc import ABC, abstractmethod

import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger("otp")


def generate_code(length: int) -> str:
    return "".join(secrets.choice("0123456789") for _ in range(length))


class OTPStore(ABC):
    """Хранилище кодов и счётчиков лимитов."""

    @abstractmethod
    async def set_code(self, phone: str, code: str, ttl: int) -> None: ...

    @abstractmethod
    async def get_code(self, phone: str) -> str | None: ...

    @abstractmethod
    async def delete_code(self, phone: str) -> None: ...

    @abstractmethod
    async def incr_attempts(self, phone: str, ttl: int) -> int: ...

    @abstractmethod
    async def clear_attempts(self, phone: str) -> None: ...

    @abstractmethod
    async def incr_requests(self, phone: str, ttl: int) -> int: ...


class MemoryOTPStore(OTPStore):
    """In-memory реализация (не для продакшна)."""

    def __init__(self) -> None:
        self._codes: dict[str, tuple[str, float]] = {}
        self._counters: dict[str, tuple[int, float]] = {}

    async def set_code(self, phone: str, code: str, ttl: int) -> None:
        self._codes[phone] = (code, time.monotonic() + ttl)

    async def get_code(self, phone: str) -> str | None:
        item = self._codes.get(phone)
        if not item:
            return None
        code, exp = item
        if time.monotonic() > exp:
            self._codes.pop(phone, None)
            return None
        return code

    async def delete_code(self, phone: str) -> None:
        self._codes.pop(phone, None)

    async def _incr(self, key: str, ttl: int) -> int:
        count, exp = self._counters.get(key, (0, 0.0))
        now = time.monotonic()
        if now > exp:
            count = 0
            exp = now + ttl
        count += 1
        self._counters[key] = (count, exp)
        return count

    async def incr_attempts(self, phone: str, ttl: int) -> int:
        return await self._incr(f"attempts:{phone}", ttl)

    async def clear_attempts(self, phone: str) -> None:
        self._counters.pop(f"attempts:{phone}", None)

    async def incr_requests(self, phone: str, ttl: int) -> int:
        return await self._incr(f"requests:{phone}", ttl)


class RedisOTPStore(OTPStore):
    """Redis-реализация для продакшна."""

    def __init__(self, redis_url: str) -> None:
        self._redis = aioredis.from_url(redis_url, decode_responses=True)

    async def set_code(self, phone: str, code: str, ttl: int) -> None:
        await self._redis.set(f"otp:code:{phone}", code, ex=ttl)

    async def get_code(self, phone: str) -> str | None:
        return await self._redis.get(f"otp:code:{phone}")

    async def delete_code(self, phone: str) -> None:
        await self._redis.delete(f"otp:code:{phone}")

    async def _incr(self, key: str, ttl: int) -> int:
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, ttl)
        return int(count)

    async def incr_attempts(self, phone: str, ttl: int) -> int:
        return await self._incr(f"otp:attempts:{phone}", ttl)

    async def clear_attempts(self, phone: str) -> None:
        await self._redis.delete(f"otp:attempts:{phone}")

    async def incr_requests(self, phone: str, ttl: int) -> int:
        return await self._incr(f"otp:requests:{phone}", ttl)


def mask_phone(phone: str) -> str:
    """Замаскировать телефон для логов: +7999•••4567."""
    if len(phone) <= 4:
        return "•" * len(phone)
    return phone[:2] + "•" * (len(phone) - 6) + phone[-4:]


def send_sms(phone: str, code: str) -> None:
    """Отправка SMS (заглушка; в проде — провайдер РФ).

    Код НИКОГДА не логируется в проде. В dev можно включить `otp_debug_log`
    для локальной отладки — тогда код виден только в незащищённом окружении.
    """
    if settings.otp_debug_log and not settings.is_prod:
        logger.info(
            "sms_otp_debug", extra={"phone": mask_phone(phone), "code": code}
        )
    else:
        logger.info("sms_otp_sent", extra={"phone": mask_phone(phone)})


# Singleton-хранилище по выбранному бэкенду.
_store: OTPStore | None = None


def get_otp_store() -> OTPStore:
    global _store
    if _store is None:
        if settings.otp_backend == "memory":
            _store = MemoryOTPStore()
        else:
            _store = RedisOTPStore(settings.redis_url)
    return _store
