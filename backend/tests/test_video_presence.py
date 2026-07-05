"""Тесты доступности видеозвонка (онлайн/запрет) и сообщений с карточки."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select

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


async def _uid(session, phone):
    return (await session.execute(
        select(User).where(User.phone == phone))).scalar_one().id


async def _match(client, otp_store, session, p1, p2):
    a = await _reg(client, otp_store, p1, "male", "female")
    b = await _reg(client, otp_store, p2, "female", "male")
    a_id, b_id = await _uid(session, p1), await _uid(session, p2)
    await client.post("/v1/discovery/like",
                      json={"target_user_id": str(b_id)}, headers=a)
    mid = (await client.post("/v1/discovery/like",
           json={"target_user_id": str(a_id)}, headers=b)).json()["match_id"]
    return a, b, mid, a_id, b_id


async def test_video_rejected_when_disabled(
    client: AsyncClient, otp_store: MemoryOTPStore, session
) -> None:
    a, b, mid, *_ = await _match(
        client, otp_store, session, "+79994441001", "+79994441002"
    )
    # B запрещает видеозвонки.
    await client.put(
        "/v1/profile", json={"video_calls_enabled": False}, headers=b
    )
    resp = await client.post(f"/v1/matches/{mid}/video", headers=a)
    assert resp.status_code == 409
    assert resp.json()["detail"]["reason"] == "disabled"


async def test_video_rejected_when_offline(
    client: AsyncClient, otp_store: MemoryOTPStore, session
) -> None:
    a, b, mid, a_id, b_id = await _match(
        client, otp_store, session, "+79994441010", "+79994441011"
    )
    # B давно не был в сети.
    b_user = await session.get(User, b_id)
    b_user.last_active_at = datetime.now(UTC) - timedelta(hours=2)
    await session.commit()

    resp = await client.post(f"/v1/matches/{mid}/video", headers=a)
    assert resp.status_code == 409
    assert resp.json()["detail"]["reason"] == "offline"

    # Состояние отражается в списке мэтчей.
    matches = (await client.get("/v1/matches", headers=a)).json()
    m = next(x for x in matches if x["match_id"] == mid)
    assert m["other_video_state"] == "offline"
    assert m["other_is_online"] is False


async def test_video_available_when_online_and_allowed(
    client: AsyncClient, otp_store: MemoryOTPStore, session
) -> None:
    a, b, mid, *_ = await _match(
        client, otp_store, session, "+79994441020", "+79994441021"
    )
    resp = await client.post(f"/v1/matches/{mid}/video", headers=a)
    assert resp.status_code == 201


async def test_discovery_card_exposes_video_state(
    client: AsyncClient, otp_store: MemoryOTPStore, session
) -> None:
    me = await _reg(client, otp_store, "+79994441030", "male", "female")
    b = await _reg(client, otp_store, "+79994441031", "female", "male")
    await client.put("/v1/profile", json={"video_calls_enabled": False}, headers=b)

    feed = (await client.get("/v1/discovery", headers=me)).json()
    card = next(c for c in feed if c["display_name"] == "1031")
    assert card["video_state"] == "disabled"
    assert card["is_online"] is True


async def test_direct_message_from_card(
    client: AsyncClient, otp_store: MemoryOTPStore, session
) -> None:
    a = await _reg(client, otp_store, "+79994441040", "male", "female")
    b = await _reg(client, otp_store, "+79994441041", "female", "male")
    b_id = await _uid(session, "+79994441041")

    # A пишет с карточки без мэтча.
    resp = await client.post(
        "/v1/discovery/message",
        json={"target_user_id": str(b_id), "body": "Привет! Понравилась анкета"},
        headers=a,
    )
    assert resp.status_code == 201
    match_id = resp.json()["match_id"]

    # Диалог виден обоим, сообщение в истории; у B — уведомление.
    b_matches = (await client.get("/v1/matches", headers=b)).json()
    assert any(m["match_id"] == match_id for m in b_matches)
    msgs = (await client.get(f"/v1/matches/{match_id}/messages", headers=b)).json()
    assert msgs[0]["body"] == "Привет! Понравилась анкета"
    notifs = (await client.get("/v1/notifications", headers=b)).json()
    assert any(n["type"] == "message" for n in notifs)

    # Повторное сообщение не создаёт второй диалог.
    resp2 = await client.post(
        "/v1/discovery/message",
        json={"target_user_id": str(b_id), "body": "Как дела?"},
        headers=a,
    )
    assert resp2.json()["match_id"] == match_id


async def test_direct_message_blocked_user_403(
    client: AsyncClient, otp_store: MemoryOTPStore, session
) -> None:
    a = await _reg(client, otp_store, "+79994441050", "male", "female")
    await _reg(client, otp_store, "+79994441051", "female", "male")
    b_id = await _uid(session, "+79994441051")
    await client.post("/v1/blocks", json={"target_user_id": str(b_id)}, headers=a)
    resp = await client.post(
        "/v1/discovery/message",
        json={"target_user_id": str(b_id), "body": "привет"},
        headers=a,
    )
    assert resp.status_code == 403
