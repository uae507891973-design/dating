"""Тесты анкеты, загрузки фото и модерации контента."""

from httpx import AsyncClient
from sqlalchemy import select

from app.models import User
from app.models.user import UserRole
from app.services.otp import MemoryOTPStore


async def _auth(client: AsyncClient, otp_store: MemoryOTPStore, phone: str) -> dict:
    await client.post("/v1/auth/request-otp", json={"phone": phone})
    code = await otp_store.get_code(phone)
    resp = await client.post("/v1/auth/verify-otp", json={"phone": phone, "code": code})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_update_profile(client: AsyncClient, otp_store: MemoryOTPStore) -> None:
    headers = await _auth(client, otp_store, "+79990000010")
    resp = await client.put(
        "/v1/profile",
        json={
            "display_name": "Анна",
            "birth_date": "1990-05-01",
            "gender": "female",
            "looking_for": "male",
            "intent": "marriage",
            "city": "Москва",
            "bio": "Люблю книги и горы",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Анна"


async def test_profile_rejects_underage(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    headers = await _auth(client, otp_store, "+79990000011")
    resp = await client.put(
        "/v1/profile", json={"birth_date": "2015-01-01"}, headers=headers
    )
    assert resp.status_code == 400


async def test_photo_auto_approved(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    headers = await _auth(client, otp_store, "+79990000012")
    files = {"file": ("ok.jpg", b"clean image bytes", "image/jpeg")}
    resp = await client.post("/v1/profile/photos", files=files, headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["moderation_status"] == "approved"
    assert body["is_primary"] is True


async def test_photo_auto_rejected(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    headers = await _auth(client, otp_store, "+79990000013")
    files = {"file": ("nsfw.jpg", b"nsfw content", "image/jpeg")}
    resp = await client.post("/v1/profile/photos", files=files, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["moderation_status"] == "rejected"


async def test_photo_sent_to_review_and_moderated(
    client: AsyncClient, otp_store: MemoryOTPStore, session
) -> None:
    phone = "+79990000014"
    headers = await _auth(client, otp_store, phone)
    files = {"file": ("review.jpg", b"review please", "image/jpeg")}
    resp = await client.post("/v1/profile/photos", files=files, headers=headers)
    assert resp.json()["moderation_status"] == "pending"
    photo_id = resp.json()["id"]

    # Обычному пользователю очередь модерации недоступна (RBAC).
    forbidden = await client.get("/v1/moderation/photos", headers=headers)
    assert forbidden.status_code == 403

    # Назначаем роль модератора и проверяем решение.
    mod_phone = "+79990000015"
    mod_headers = await _auth(client, otp_store, mod_phone)
    user = (
        await session.execute(select(User).where(User.phone == mod_phone))
    ).scalar_one()
    user.role = UserRole.moderator
    await session.commit()

    queue = await client.get("/v1/moderation/photos", headers=mod_headers)
    assert queue.status_code == 200
    assert any(p["id"] == photo_id for p in queue.json())

    decision = await client.post(
        f"/v1/moderation/photos/{photo_id}/decision",
        json={"decision": "approved", "reason": "ok"},
        headers=mod_headers,
    )
    assert decision.status_code == 200
    assert decision.json()["moderation_status"] == "approved"
