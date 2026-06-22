"""Тесты антифрод-движка: сигналы, trust-score, авто-флаги."""

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


async def _promote_moderator(client, otp_store, session, phone) -> dict:
    headers = await _auth(client, otp_store, phone)
    user = (
        await session.execute(select(User).where(User.phone == phone))
    ).scalar_one()
    user.role = UserRole.moderator
    await session.commit()
    return headers


async def test_spam_messages_trigger_autoflag(
    client: AsyncClient, otp_store: MemoryOTPStore, session
) -> None:
    a = await _setup(client, otp_store, "+79994440001", "male", "female")
    b = await _setup(client, otp_store, "+79994440002", "female", "male")
    a_id = (
        await session.execute(select(User).where(User.phone == "+79994440001"))
    ).scalar_one().id
    b_id = (
        await session.execute(select(User).where(User.phone == "+79994440002"))
    ).scalar_one().id
    await client.post(
        "/v1/discovery/like", json={"target_user_id": str(b_id)}, headers=a
    )
    match_id = (
        await client.post(
            "/v1/discovery/like", json={"target_user_id": str(a_id)}, headers=b
        )
    ).json()["match_id"]

    # Шаблонный спам: много одинаковых сообщений (velocity + duplicates).
    for _ in range(21):
        await client.post(
            f"/v1/matches/{match_id}/messages",
            json={"body": "купи курс по ссылке"},
            headers=a,
        )

    mod = await _promote_moderator(client, otp_store, session, "+79994440003")
    flags = await client.get("/v1/moderation/flags", headers=mod)
    assert flags.status_code == 200
    flagged_users = {f["user_id"] for f in flags.json()}
    assert str(a_id) in flagged_users

    flag = next(f for f in flags.json() if f["user_id"] == str(a_id))
    assert flag["risk_score"] >= 50
    assert flag["reasons"]

    # Резолв флага.
    resolved = await client.post(
        f"/v1/moderation/flags/{flag['id']}/resolve", headers=mod
    )
    assert resolved.json()["status"] == "resolved"


async def test_reports_increase_risk_on_scan(
    client: AsyncClient, otp_store: MemoryOTPStore, session
) -> None:
    await _setup(client, otp_store, "+79994440010", "female", "male")
    target_id = (
        await session.execute(select(User).where(User.phone == "+79994440010"))
    ).scalar_one().id

    # Три разных пользователя жалуются на target.
    for i in range(3):
        reporter = await _auth(client, otp_store, f"+7999444002{i}")
        await client.post(
            "/v1/reports",
            json={"target_user_id": str(target_id), "reason": "мошенник"},
            headers=reporter,
        )

    mod = await _promote_moderator(client, otp_store, session, "+79994440030")
    scan = await client.post(
        f"/v1/moderation/antifraud/scan/{target_id}", headers=mod
    )
    assert scan.status_code == 200
    body = scan.json()
    assert body["risk_score"] >= 40
    assert body["trust_score"] <= 60
    assert any("жалоб" in r for r in body["reasons"])


async def test_clean_user_not_flagged(
    client: AsyncClient, otp_store: MemoryOTPStore, session
) -> None:
    await _setup(client, otp_store, "+79994440040", "female", "male")
    target_id = (
        await session.execute(select(User).where(User.phone == "+79994440040"))
    ).scalar_one().id
    mod = await _promote_moderator(client, otp_store, session, "+79994440041")
    scan = await client.post(
        f"/v1/moderation/antifraud/scan/{target_id}", headers=mod
    )
    assert scan.json()["risk_score"] == 0
    assert scan.json()["trust_score"] == 100


async def test_flags_require_moderator(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    headers = await _auth(client, otp_store, "+79994440050")
    resp = await client.get("/v1/moderation/flags", headers=headers)
    assert resp.status_code == 403
