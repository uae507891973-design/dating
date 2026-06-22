"""Тесты объяснимого мэтчинга и scrutability."""

from httpx import AsyncClient

from app.models.profile import Intent
from app.services.compatibility import CompatibilityResult
from app.services.explain import generate_reasons
from app.services.otp import MemoryOTPStore


def test_reasons_include_intent_and_top_categories() -> None:
    compat = CompatibilityResult(
        score=90,
        category_contributions={"values": 0.95, "goals": 0.8, "lifestyle": 0.2},
        common_questions=16,
    )
    reasons = generate_reasons(compat, Intent.marriage, Intent.marriage)
    assert reasons[0] == "оба настроены на создание семьи"
    assert any("ценности" in r.lower() for r in reasons)
    # Слабая категория (lifestyle 0.2) не попадает в причины.
    assert all("образ жизни" not in r.lower() for r in reasons)
    assert len(reasons) <= 3


def test_reasons_empty_when_no_strong_factors() -> None:
    compat = CompatibilityResult(
        score=30,
        category_contributions={"values": 0.3, "goals": 0.2},
        common_questions=16,
    )
    assert generate_reasons(compat, None, None) == []


async def _auth(client: AsyncClient, otp_store: MemoryOTPStore, phone: str) -> dict:
    await client.post("/v1/auth/request-otp", json={"phone": phone})
    code = await otp_store.get_code(phone)
    resp = await client.post("/v1/auth/verify-otp", json={"phone": phone, "code": code})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _setup(
    client: AsyncClient,
    otp_store: MemoryOTPStore,
    phone: str,
    gender: str,
    looking_for: str,
    answer_for_category,
) -> dict:
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
        {
            "question_id": q["id"],
            "value": answer_for_category(q["category"]),
            "importance": "high",
        }
        for q in questions
    ]
    await client.post(
        "/v1/onboarding/answers",
        json={"answers": answers, "intent": "marriage"},
        headers=headers,
    )
    return headers


async def test_reasons_present_in_discovery(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    me = await _setup(client, otp_store, "+79992220001", "male", "female", lambda c: 5)
    await _setup(client, otp_store, "+79992220002", "female", "male", lambda c: 5)
    resp = await client.get("/v1/discovery", headers=me)
    cand = resp.json()[0]
    assert cand["score"] == 100
    assert cand["reasons"]  # есть объяснения


async def test_scrutability_changes_ranking(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    # Кандидат совпадает везде, кроме lifestyle (там расходятся).
    me = await _setup(client, otp_store, "+79992220010", "male", "female", lambda c: 5)
    await _setup(
        client,
        otp_store,
        "+79992220011",
        "female",
        "male",
        lambda c: 1 if c == "lifestyle" else 5,
    )

    baseline = (await client.get("/v1/discovery", headers=me)).json()[0]["score"]

    # Приглушаем lifestyle — общий счёт должен вырасти.
    await client.put(
        "/v1/discovery/preferences",
        json=[{"category": "lifestyle", "importance": "muted"}],
        headers=me,
    )
    muted = (await client.get("/v1/discovery", headers=me)).json()[0]["score"]
    assert muted > baseline

    # Делаем lifestyle важным — счёт должен упасть ниже базового.
    await client.put(
        "/v1/discovery/preferences",
        json=[{"category": "lifestyle", "importance": "important"}],
        headers=me,
    )
    important = (await client.get("/v1/discovery", headers=me)).json()[0]["score"]
    assert important < baseline


async def test_set_preferences_rejects_unknown_category(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    headers = await _auth(client, otp_store, "+79992220020")
    resp = await client.put(
        "/v1/discovery/preferences",
        json=[{"category": "nope", "importance": "important"}],
        headers=headers,
    )
    assert resp.status_code == 400
