"""Тесты онбординга: тест совместимости и намерение."""

from httpx import AsyncClient

from app.services.otp import MemoryOTPStore

PHONE = "+79990000001"


async def _auth_headers(client: AsyncClient, otp_store: MemoryOTPStore) -> dict:
    await client.post("/v1/auth/request-otp", json={"phone": PHONE})
    code = await otp_store.get_code(PHONE)
    resp = await client.post(
        "/v1/auth/verify-otp", json={"phone": PHONE, "code": code}
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_get_questions(client: AsyncClient) -> None:
    resp = await client.get("/v1/onboarding/questions")
    assert resp.status_code == 200
    questions = resp.json()
    assert len(questions) >= 16
    assert {"id", "category", "text", "options"} <= set(questions[0])


async def test_submit_answers_and_status(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    headers = await _auth_headers(client, otp_store)
    questions = (await client.get("/v1/onboarding/questions")).json()
    answers = [
        {"question_id": q["id"], "value": 4, "importance": "high"}
        for q in questions
    ]

    resp = await client.post(
        "/v1/onboarding/answers",
        json={"answers": answers, "intent": "marriage"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["test_completed"] is True
    assert body["answered_count"] == len(answers)
    assert body["intent"] == "marriage"
    assert body["psychoprofile"]  # вектор по категориям непустой

    status_resp = await client.get("/v1/onboarding/status", headers=headers)
    assert status_resp.status_code == 200
    assert status_resp.json()["test_completed"] is True


async def test_submit_unknown_question_rejected(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    headers = await _auth_headers(client, otp_store)
    resp = await client.post(
        "/v1/onboarding/answers",
        json={
            "answers": [{"question_id": "does_not_exist", "value": 3}],
            "intent": "relationship",
        },
        headers=headers,
    )
    assert resp.status_code == 400


async def test_submit_requires_auth(client: AsyncClient) -> None:
    resp = await client.post(
        "/v1/onboarding/answers",
        json={
            "answers": [{"question_id": "val_shared", "value": 3}],
            "intent": "friendship",
        },
    )
    assert resp.status_code == 401
