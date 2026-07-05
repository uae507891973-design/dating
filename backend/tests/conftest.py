"""Фикстуры тестов."""

import os
import tempfile

# Тестовое окружение должно быть задано до импорта приложения/настроек.
os.environ.setdefault("OTP_BACKEND", "memory")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("MEDIA_DIR", tempfile.mkdtemp(prefix="davinci-media-"))

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.otp import MemoryOTPStore, get_otp_store  # noqa: E402
from app.services.ratelimit import (  # noqa: E402
    MemoryRateLimiter,
    get_rate_limiter,
)

test_engine = create_async_engine(
    "sqlite+aiosqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def _setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def otp_store() -> MemoryOTPStore:
    return MemoryOTPStore()


@pytest.fixture
async def session():
    """Прямой доступ к тестовой БД (для подготовки данных)."""
    async with TestSession() as s:
        yield s


@pytest.fixture
async def client(otp_store: MemoryOTPStore) -> AsyncClient:
    async def _override_get_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_otp_store] = lambda: otp_store
    # Свежий in-memory rate-limiter на каждый тест (без утечки между тестами).
    limiter = MemoryRateLimiter()
    app.dependency_overrides[get_rate_limiter] = lambda: limiter

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
