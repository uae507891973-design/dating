"""Тесты Этапа D: security-заголовки, авто-истечение видео, rate-limit."""

from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import get_settings
from app.models import User
from app.services.otp import MemoryOTPStore


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


async def _match(client, otp_store, session, p1, p2):
    a = await _reg(client, otp_store, p1, "male", "female")
    b = await _reg(client, otp_store, p2, "female", "male")
    a_id = (await session.execute(
        select(User).where(User.phone == p1))).scalar_one().id
    b_id = (await session.execute(
        select(User).where(User.phone == p2))).scalar_one().id
    await client.post("/v1/discovery/like",
                      json={"target_user_id": str(b_id)}, headers=a)
    mid = (await client.post("/v1/discovery/like",
           json={"target_user_id": str(a_id)}, headers=b)).json()["match_id"]
    return a, b, mid


async def test_security_headers_present(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"


async def test_message_rate_limit(
    client: AsyncClient, otp_store: MemoryOTPStore, session
) -> None:
    a, b, mid = await _match(client, otp_store, session, "+79993331001", "+79993331002")
    settings = get_settings()
    orig = settings.message_rate_max
    try:
        settings.message_rate_max = 2
        r1 = await client.post(f"/v1/matches/{mid}/messages",
                               json={"body": "1"}, headers=a)
        r2 = await client.post(f"/v1/matches/{mid}/messages",
                               json={"body": "2"}, headers=a)
        r3 = await client.post(f"/v1/matches/{mid}/messages",
                               json={"body": "3"}, headers=a)
        assert r1.status_code == 201 and r2.status_code == 201
        assert r3.status_code == 429
    finally:
        settings.message_rate_max = orig


async def test_video_request_auto_expires(
    client: AsyncClient, otp_store: MemoryOTPStore, session
) -> None:
    a, b, mid = await _match(client, otp_store, session, "+79993331010", "+79993331011")
    sid = (await client.post(f"/v1/matches/{mid}/video", headers=a)).json()["id"]
    settings = get_settings()
    orig = settings.video_request_ttl_sec
    try:
        settings.video_request_ttl_sec = -1  # мгновенное истечение
        got = await client.get(f"/v1/video/{sid}", headers=a)
        assert got.json()["status"] == "declined"
    finally:
        settings.video_request_ttl_sec = orig
