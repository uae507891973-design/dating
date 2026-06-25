"""Тесты движка подбора: фильтры, ранжирование, лайки и мэтчи."""

from httpx import AsyncClient

from app.services.otp import MemoryOTPStore


async def _auth(client: AsyncClient, otp_store: MemoryOTPStore, phone: str) -> dict:
    await client.post("/v1/auth/request-otp", json={"phone": phone})
    code = await otp_store.get_code(phone)
    resp = await client.post(
        "/v1/auth/verify-otp",
        json={"phone": phone, "code": code, "accepted_documents": ["privacy", "terms"]},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _setup_user(
    client: AsyncClient,
    otp_store: MemoryOTPStore,
    phone: str,
    gender: str,
    looking_for: str,
    answer_value: int,
) -> dict:
    headers = await _auth(client, otp_store, phone)
    await client.put(
        "/v1/profile",
        json={
            "display_name": phone[-4:],
            "birth_date": "1992-01-01",
            "gender": gender,
            "looking_for": looking_for,
            "intent": "relationship",
            "city": "Москва",
        },
        headers=headers,
    )
    questions = (await client.get("/v1/onboarding/questions")).json()
    answers = [
        {"question_id": q["id"], "value": answer_value, "importance": "high"}
        for q in questions
    ]
    await client.post(
        "/v1/onboarding/answers",
        json={"answers": answers, "intent": "relationship"},
        headers=headers,
    )
    return headers


async def test_discovery_filters_and_ranking(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    # Я — мужчина, ищу женщин.
    me = await _setup_user(client, otp_store, "+79991110001", "male", "female", 5)
    # Близкая по ответам женщина (высокая совместимость).
    await _setup_user(client, otp_store, "+79991110002", "female", "male", 5)
    # Далёкая по ответам женщина (низкая совместимость).
    await _setup_user(client, otp_store, "+79991110003", "female", "male", 1)
    # Мужчина — не должен попасть в подборку (фильтр по полу).
    await _setup_user(client, otp_store, "+79991110004", "male", "female", 5)

    resp = await client.get("/v1/discovery", headers=me)
    assert resp.status_code == 200
    candidates = resp.json()
    names = [c["display_name"] for c in candidates]
    assert "0002" in names and "0003" in names
    assert "0004" not in names  # отфильтрован по полу
    # Ранжирование: более совместимая выше.
    assert names.index("0002") < names.index("0003")
    assert candidates[names.index("0002")]["score"] == 100


async def test_like_creates_match_on_reciprocity(
    client: AsyncClient, otp_store: MemoryOTPStore, session
) -> None:
    from sqlalchemy import select

    from app.models import User

    a = await _setup_user(client, otp_store, "+79991110010", "male", "female", 4)
    b = await _setup_user(client, otp_store, "+79991110011", "female", "male", 4)

    a_id = (
        await session.execute(select(User).where(User.phone == "+79991110010"))
    ).scalar_one().id
    b_id = (
        await session.execute(select(User).where(User.phone == "+79991110011"))
    ).scalar_one().id

    # A лайкает B — мэтча ещё нет.
    r1 = await client.post(
        "/v1/discovery/like", json={"target_user_id": str(b_id)}, headers=a
    )
    assert r1.json()["matched"] is False

    # B лайкает A — образуется мэтч.
    r2 = await client.post(
        "/v1/discovery/like", json={"target_user_id": str(a_id)}, headers=b
    )
    assert r2.json()["matched"] is True
    assert r2.json()["match_id"]


async def test_skipped_user_excluded_from_discovery(
    client: AsyncClient, otp_store: MemoryOTPStore, session
) -> None:
    from sqlalchemy import select

    from app.models import User

    me = await _setup_user(client, otp_store, "+79991110020", "male", "female", 5)
    await _setup_user(client, otp_store, "+79991110021", "female", "male", 5)
    target_id = (
        await session.execute(select(User).where(User.phone == "+79991110021"))
    ).scalar_one().id

    before = await client.get("/v1/discovery", headers=me)
    assert any(c["user_id"] == str(target_id) for c in before.json())

    await client.post(
        "/v1/discovery/skip", json={"target_user_id": str(target_id)}, headers=me
    )
    after = await client.get("/v1/discovery", headers=me)
    assert all(c["user_id"] != str(target_id) for c in after.json())


async def test_cannot_like_self(
    client: AsyncClient, otp_store: MemoryOTPStore, session
) -> None:
    from sqlalchemy import select

    from app.models import User

    me = await _setup_user(client, otp_store, "+79991110030", "male", "female", 3)
    my_id = (
        await session.execute(select(User).where(User.phone == "+79991110030"))
    ).scalar_one().id
    resp = await client.post(
        "/v1/discovery/like", json={"target_user_id": str(my_id)}, headers=me
    )
    assert resp.status_code == 400
