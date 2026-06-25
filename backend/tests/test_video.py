"""Тесты видеознакомства «вслепую»."""

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


async def _make_match(client, otp_store, session, p1, p2):
    a = await _setup(client, otp_store, p1, "male", "female")
    b = await _setup(client, otp_store, p2, "female", "male")
    a_id = (
        await session.execute(select(User).where(User.phone == p1))
    ).scalar_one().id
    b_id = (
        await session.execute(select(User).where(User.phone == p2))
    ).scalar_one().id
    await client.post(
        "/v1/discovery/like", json={"target_user_id": str(b_id)}, headers=a
    )
    match_id = (
        await client.post(
            "/v1/discovery/like", json={"target_user_id": str(a_id)}, headers=b
        )
    ).json()["match_id"]
    return a, b, match_id, a_id, b_id


async def test_video_full_flow_reveal_and_trust(
    client: AsyncClient, otp_store: MemoryOTPStore, session
) -> None:
    a, b, match_id, a_id, b_id = await _make_match(
        client, otp_store, session, "+79995550001", "+79995550002"
    )

    # Инициация (A) и принятие (B).
    init = await client.post(f"/v1/matches/{match_id}/video", headers=a)
    assert init.status_code == 201
    sid = init.json()["id"]
    assert init.json()["blur_level"] == 1.0

    acc = await client.post(f"/v1/video/{sid}/accept", headers=b)
    assert acc.json()["status"] == "active"

    # Управление блюром.
    blur = await client.post(
        f"/v1/video/{sid}/blur", json={"level": 0.5}, headers=b
    )
    assert blur.json()["blur_level"] == 0.5

    # Обоюдное согласие на раскрытие.
    await client.post(f"/v1/video/{sid}/continue", json={"yes": True}, headers=a)
    rev = await client.post(
        f"/v1/video/{sid}/continue", json={"yes": True}, headers=b
    )
    assert rev.json()["revealed"] is True
    assert rev.json()["blur_level"] == 0.0

    # Завершение → бонус к trust-score обоим.
    end = await client.post(f"/v1/video/{sid}/end", headers=a)
    assert end.json()["status"] == "ended"

    a_user = (
        await session.execute(select(User).where(User.id == a_id))
    ).scalar_one()
    await session.refresh(a_user)
    assert a_user.trust_score >= 100  # был 100, бонус capped


async def test_initiator_cannot_accept(
    client: AsyncClient, otp_store: MemoryOTPStore, session
) -> None:
    a, b, match_id, *_ = await _make_match(
        client, otp_store, session, "+79995550010", "+79995550011"
    )
    sid = (await client.post(f"/v1/matches/{match_id}/video", headers=a)).json()["id"]
    resp = await client.post(f"/v1/video/{sid}/accept", headers=a)
    assert resp.status_code == 400


async def test_duplicate_active_session_rejected(
    client: AsyncClient, otp_store: MemoryOTPStore, session
) -> None:
    a, b, match_id, *_ = await _make_match(
        client, otp_store, session, "+79995550020", "+79995550021"
    )
    await client.post(f"/v1/matches/{match_id}/video", headers=a)
    dup = await client.post(f"/v1/matches/{match_id}/video", headers=a)
    assert dup.status_code == 409


async def test_decline_video(
    client: AsyncClient, otp_store: MemoryOTPStore, session
) -> None:
    a, b, match_id, *_ = await _make_match(
        client, otp_store, session, "+79995550030", "+79995550031"
    )
    sid = (await client.post(f"/v1/matches/{match_id}/video", headers=a)).json()["id"]
    resp = await client.post(f"/v1/video/{sid}/decline", headers=b)
    assert resp.json()["status"] == "declined"


async def test_non_participant_cannot_access_session(
    client: AsyncClient, otp_store: MemoryOTPStore, session
) -> None:
    a, b, match_id, *_ = await _make_match(
        client, otp_store, session, "+79995550040", "+79995550041"
    )
    sid = (await client.post(f"/v1/matches/{match_id}/video", headers=a)).json()["id"]
    outsider = await _auth(client, otp_store, "+79995550099")
    resp = await client.get(f"/v1/video/{sid}", headers=outsider)
    assert resp.status_code == 403
