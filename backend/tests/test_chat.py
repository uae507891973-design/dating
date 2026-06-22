"""Тесты чата: сообщения, доступ, айсбрейкеры, модерация."""

import uuid

from httpx import AsyncClient
from sqlalchemy import select

from app.models import User
from app.services.chat import generate_icebreakers, screen_message
from app.services.otp import MemoryOTPStore


def test_screen_message_blocks_empty() -> None:
    ok, reason = screen_message("   ", True)
    assert ok is False


def test_screen_message_blocks_links_for_unverified() -> None:
    ok, _ = screen_message("пиши мне t.me/spam", False)
    assert ok is False
    # Верифицированному — можно.
    ok2, _ = screen_message("пиши мне t.me/ok", True)
    assert ok2 is True


def test_icebreakers_from_strong_categories() -> None:
    s = generate_icebreakers({"values": 0.9, "family": 0.8, "lifestyle": 0.1}, "Аня")
    assert s
    assert len(s) <= 3


async def _auth(client: AsyncClient, otp_store: MemoryOTPStore, phone: str) -> dict:
    await client.post("/v1/auth/request-otp", json={"phone": phone})
    code = await otp_store.get_code(phone)
    resp = await client.post("/v1/auth/verify-otp", json={"phone": phone, "code": code})
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


async def _make_match(client, otp_store, session) -> tuple[dict, dict, str]:
    a = await _setup(client, otp_store, "+79993330001", "male", "female")
    b = await _setup(client, otp_store, "+79993330002", "female", "male")
    a_id = (
        await session.execute(select(User).where(User.phone == "+79993330001"))
    ).scalar_one().id
    b_id = (
        await session.execute(select(User).where(User.phone == "+79993330002"))
    ).scalar_one().id
    await client.post(
        "/v1/discovery/like", json={"target_user_id": str(b_id)}, headers=a
    )
    r = await client.post(
        "/v1/discovery/like", json={"target_user_id": str(a_id)}, headers=b
    )
    return a, b, r.json()["match_id"]


async def test_send_and_list_messages(
    client: AsyncClient, otp_store: MemoryOTPStore, session
) -> None:
    a, b, match_id = await _make_match(client, otp_store, session)

    send = await client.post(
        f"/v1/matches/{match_id}/messages",
        json={"body": "Привет! Рад мэтчу"},
        headers=a,
    )
    assert send.status_code == 201

    # Собеседник видит сообщение в истории.
    msgs = await client.get(f"/v1/matches/{match_id}/messages", headers=b)
    assert msgs.status_code == 200
    assert msgs.json()[0]["body"] == "Привет! Рад мэтчу"

    # Отметка прочтения.
    read = await client.post(f"/v1/matches/{match_id}/read", headers=b)
    assert read.status_code == 204


async def test_matches_list(
    client: AsyncClient, otp_store: MemoryOTPStore, session
) -> None:
    a, _, match_id = await _make_match(client, otp_store, session)
    resp = await client.get("/v1/matches", headers=a)
    assert resp.status_code == 200
    assert any(m["match_id"] == match_id for m in resp.json())


async def test_icebreakers_endpoint(
    client: AsyncClient, otp_store: MemoryOTPStore, session
) -> None:
    a, _, match_id = await _make_match(client, otp_store, session)
    resp = await client.get(f"/v1/matches/{match_id}/icebreakers", headers=a)
    assert resp.status_code == 200
    assert resp.json()["suggestions"]


async def test_non_participant_cannot_access(
    client: AsyncClient, otp_store: MemoryOTPStore, session
) -> None:
    _, _, match_id = await _make_match(client, otp_store, session)
    outsider = await _auth(client, otp_store, "+79993330099")
    resp = await client.get(f"/v1/matches/{match_id}/messages", headers=outsider)
    assert resp.status_code == 403


async def test_message_to_missing_match_404(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    headers = await _auth(client, otp_store, "+79993330100")
    resp = await client.get(
        f"/v1/matches/{uuid.uuid4()}/messages", headers=headers
    )
    assert resp.status_code == 404
