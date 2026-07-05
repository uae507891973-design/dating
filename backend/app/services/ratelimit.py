"""Общий rate-limiter действий (лайки/сообщения).

Два бэкенда: Redis (прод) и in-memory (тесты/локально). Метод `hit` возвращает
True, если лимит превышен (действие нужно отклонить).
"""

import time
from abc import ABC, abstractmethod

import redis.asyncio as aioredis

from app.core.config import get_settings

settings = get_settings()


class RateLimiter(ABC):
    @abstractmethod
    async def hit(self, key: str, max_hits: int, window_sec: int) -> bool: ...


class MemoryRateLimiter(RateLimiter):
    def __init__(self) -> None:
        self._counters: dict[str, tuple[int, float]] = {}

    async def hit(self, key: str, max_hits: int, window_sec: int) -> bool:
        count, exp = self._counters.get(key, (0, 0.0))
        now = time.monotonic()
        if now > exp:
            count, exp = 0, now + window_sec
        count += 1
        self._counters[key] = (count, exp)
        return count > max_hits


class RedisRateLimiter(RateLimiter):
    def __init__(self, redis_url: str) -> None:
        self._redis = aioredis.from_url(redis_url, decode_responses=True)

    async def hit(self, key: str, max_hits: int, window_sec: int) -> bool:
        count = await self._redis.incr(f"rl:{key}")
        if count == 1:
            await self._redis.expire(f"rl:{key}", window_sec)
        return int(count) > max_hits


_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        if settings.ratelimit_backend == "memory":
            _limiter = MemoryRateLimiter()
        else:
            _limiter = RedisRateLimiter(settings.redis_url)
    return _limiter
