"""Тесты Этапа A (критическая безопасность): guard, OTP, блокировки, маскирование."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models import User
from app.services.otp import MemoryOTPStore, mask_phone


# --- A1: маскирование телефона в логах ---
def test_mask_phone_hides_middle() -> None:
    masked = mask_phone("+79991234567")
    assert masked.startswith("+7")
    assert masked.endswith("4567")
    assert "999123" not in masked
    assert "•" in masked


# --- A2: guard небезопасной prod-конфигурации ---
def test_prod_guard_rejects_default_secret() -> None:
    from app.main import settings, validate_prod_settings

    orig = (settings.environment, settings.jwt_secret, settings.debug,
            settings.otp_debug_log, settings.pii_secret)
    try:
        settings.environment = "prod"
        settings.debug = False
        settings.otp_debug_log = False
        settings.pii_secret = "p" * 40
        settings.jwt_secret = "change-me-in-prod"
        with pytest.raises(RuntimeError):
            validate_prod_settings()
        # Надёжные секреты — проходит.
        settings.jwt_secret = "x" * 40
        validate_prod_settings()
    finally:
        (settings.environment, settings.jwt_secret, settings.debug,
         settings.otp_debug_log, settings.pii_secret) = orig


# --- A5: OTP 6 цифр, сброс попыток при новом коде, код жертвы не удаляется ---
async def test_otp_is_six_digits(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    phone = "+79997770000"
    await client.post("/v1/auth/request-otp", json={"phone": phone})
    code = await otp_store.get_code(phone)
    assert code is not None and len(code) == 6 and code.isdigit()


async def test_otp_lockout_recovers_with_new_code(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    phone = "+79997770001"
    await client.post("/v1/auth/request-otp", json={"phone": phone})
    real = await otp_store.get_code(phone)
    wrong = "000000" if real != "000000" else "111111"

    last = None
    for _ in range(6):
        last = await client.post(
            "/v1/auth/verify-otp", json={"phone": phone, "code": wrong}
        )
    assert last.status_code == 429  # попытки исчерпаны

    # Легитимный пользователь запрашивает новый код — попытки сбрасываются.
    await client.post("/v1/auth/request-otp", json={"phone": phone})
    new_code = await otp_store.get_code(phone)
    resp = await client.post(
        "/v1/auth/verify-otp",
        json={"phone": phone, "code": new_code,
              "accepted_documents": ["privacy", "terms"]},
    )
    assert resp.status_code == 200


# --- A4: блокировка прекращает контакт ---
async def _reg(client, otp_store, phone, gender, looking_for):
    await client.post("/v1/auth/request-otp", json={"phone": phone})
    code = await otp_store.get_code(phone)
    r = await client.post(
        "/v1/auth/verify-otp",
        json={"phone": phone, "code": code,
              "accepted_documents": ["privacy", "terms"]},
    )
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    await client.put(
        "/v1/profile",
        json={"display_name": phone[-4:], "birth_date": "1992-01-01",
              "gender": gender, "looking_for": looking_for, "intent": "marriage"},
        headers=headers,
    )
    q = (await client.get("/v1/onboarding/questions")).json()
    await client.post(
        "/v1/onboarding/answers",
        json={"answers": [{"question_id": x["id"], "value": 5} for x in q],
              "intent": "marriage"},
        headers=headers,
    )
    return headers


async def test_phone_encrypted_at_rest(
    client: AsyncClient, otp_store: MemoryOTPStore, session
) -> None:
    from sqlalchemy import text

    phone = "+79997770100"
    await client.post("/v1/auth/request-otp", json={"phone": phone})
    code = await otp_store.get_code(phone)
    await client.post(
        "/v1/auth/verify-otp",
        json={"phone": phone, "code": code,
              "accepted_documents": ["privacy", "terms"]},
    )
    # Сырое значение в БД не равно открытому телефону.
    raw = (await session.execute(text("SELECT phone FROM users"))).scalars().all()
    assert phone not in raw
    assert all(phone != r for r in raw)

    # Но ORM-поиск по открытому телефону работает (детерминированное шифрование).
    found = (await session.execute(
        select(User).where(User.phone == phone))).scalar_one()
    assert found.phone == phone


async def _tokens(client, otp_store, phone):
    await client.post("/v1/auth/request-otp", json={"phone": phone})
    code = await otp_store.get_code(phone)
    r = await client.post(
        "/v1/auth/verify-otp",
        json={"phone": phone, "code": code,
              "accepted_documents": ["privacy", "terms"]},
    )
    return r.json()


async def test_logout_revokes_access_token(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    t = await _tokens(client, otp_store, "+79997770020")
    headers = {"Authorization": f"Bearer {t['access_token']}"}

    # Токен работает.
    assert (await client.get("/v1/consents", headers=headers)).status_code == 200
    # Logout.
    assert (await client.post("/v1/auth/logout", headers=headers)).status_code == 204
    # Тот же токен больше не принимается.
    assert (await client.get("/v1/consents", headers=headers)).status_code == 401


async def test_refresh_revoked_after_logout(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    t = await _tokens(client, otp_store, "+79997770021")
    headers = {"Authorization": f"Bearer {t['access_token']}"}
    await client.post("/v1/auth/logout", headers=headers)

    resp = await client.post(
        "/v1/auth/refresh", json={"refresh_token": t["refresh_token"]}
    )
    assert resp.status_code == 401


async def test_block_prevents_contact(
    client: AsyncClient, otp_store: MemoryOTPStore, session
) -> None:
    a = await _reg(client, otp_store, "+79997770010", "male", "female")
    b = await _reg(client, otp_store, "+79997770011", "female", "male")
    a_id = (await session.execute(
        select(User).where(User.phone == "+79997770010"))).scalar_one().id
    b_id = (await session.execute(
        select(User).where(User.phone == "+79997770011"))).scalar_one().id

    await client.post("/v1/discovery/like",
                      json={"target_user_id": str(b_id)}, headers=a)
    match_id = (await client.post(
        "/v1/discovery/like", json={"target_user_id": str(a_id)}, headers=b
    )).json()["match_id"]

    # A блокирует B.
    await client.post("/v1/blocks", json={"target_user_id": str(b_id)}, headers=a)

    # Сообщение и видео — запрещены в обе стороны.
    m1 = await client.post(f"/v1/matches/{match_id}/messages",
                           json={"body": "привет"}, headers=a)
    assert m1.status_code == 403
    m2 = await client.post(f"/v1/matches/{match_id}/messages",
                           json={"body": "привет"}, headers=b)
    assert m2.status_code == 403
    v = await client.post(f"/v1/matches/{match_id}/video", headers=b)
    assert v.status_code == 403

    # Лайк заблокированного — тоже запрещён.
    like = await client.post("/v1/discovery/like",
                             json={"target_user_id": str(a_id)}, headers=b)
    assert like.status_code == 403
