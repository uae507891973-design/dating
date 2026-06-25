"""Тесты уведомлений: устройства, in-app, привязка к событиям."""

from httpx import AsyncClient
from sqlalchemy import select

from app.models import User
from app.services.otp import MemoryOTPStore


async def _auth(client: AsyncClient, otp_store: MemoryOTPStore, phone: str) -> dict:
    await client.post("/v1/auth/request-otp", json={"phone": phone})
    code = await otp_store.get_code(phone)
    resp = await client.post(
        "/v1/auth/verify-otp",
        json={"phone": phone, "code": code, "accepted_documents": ["privacy", "terms"]},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _setup(client, otp_store, phone, gender, looking_for) -> dict:
    headers = await _auth(client, otp_store, phone)
    await client.put(
        "/v1/profile",
        json={
            "display_name": phone[-4:],
            "birth_date": "1992-01-01",
            "gender": gender,
            "looking_for": looking_for,
            "intent": "marriage",
        },
        headers=headers,
    )
    questions = (await client.get("/v1/onboarding/questions")).json()
    answers = [
        {"question_id": q["id"], "value": 5, "importance": "high"} for q in questions
    ]
    await client.post(
        "/v1/onboarding/answers",
        json={"answers": answers, "intent": "marriage"},
        headers=headers,
    )
    return headers


async def test_register_device(client: AsyncClient, otp_store: MemoryOTPStore) -> None:
    headers = await _auth(client, otp_store, "+79996660001")
    resp = await client.post(
        "/v1/devices",
        json={"token": "device-token-123", "platform": "android"},
        headers=headers,
    )
    assert resp.status_code == 204


async def test_register_device_validates_platform(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    headers = await _auth(client, otp_store, "+79996660002")
    resp = await client.post(
        "/v1/devices",
        json={"token": "device-token-456", "platform": "symbian"},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_match_generates_notifications(
    client: AsyncClient, otp_store: MemoryOTPStore, session
) -> None:
    a = await _setup(client, otp_store, "+79996660010", "male", "female")
    b = await _setup(client, otp_store, "+79996660011", "female", "male")
    a_id = (
        await session.execute(select(User).where(User.phone == "+79996660010"))
    ).scalar_one().id
    b_id = (
        await session.execute(select(User).where(User.phone == "+79996660011"))
    ).scalar_one().id

    await client.post(
        "/v1/discovery/like", json={"target_user_id": str(b_id)}, headers=a
    )
    await client.post(
        "/v1/discovery/like", json={"target_user_id": str(a_id)}, headers=b
    )

    # Оба участника получили уведомление о мэтче.
    a_notifs = (await client.get("/v1/notifications", headers=a)).json()
    b_notifs = (await client.get("/v1/notifications", headers=b)).json()
    assert any(n["type"] == "match" for n in a_notifs)
    assert any(n["type"] == "match" for n in b_notifs)


async def test_message_notifies_recipient_and_mark_read(
    client: AsyncClient, otp_store: MemoryOTPStore, session
) -> None:
    a = await _setup(client, otp_store, "+79996660020", "male", "female")
    b = await _setup(client, otp_store, "+79996660021", "female", "male")
    a_id = (
        await session.execute(select(User).where(User.phone == "+79996660020"))
    ).scalar_one().id
    b_id = (
        await session.execute(select(User).where(User.phone == "+79996660021"))
    ).scalar_one().id
    await client.post(
        "/v1/discovery/like", json={"target_user_id": str(b_id)}, headers=a
    )
    match_id = (
        await client.post(
            "/v1/discovery/like", json={"target_user_id": str(a_id)}, headers=b
        )
    ).json()["match_id"]

    await client.post(
        f"/v1/matches/{match_id}/messages", json={"body": "Привет"}, headers=a
    )

    # B получает уведомление о сообщении (фильтр непрочитанных).
    unread = (
        await client.get("/v1/notifications?only_unread=true", headers=b)
    ).json()
    msg_notifs = [n for n in unread if n["type"] == "message"]
    assert msg_notifs

    read = await client.post(
        f"/v1/notifications/{msg_notifs[0]['id']}/read", headers=b
    )
    assert read.status_code == 204
