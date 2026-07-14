"""Тесты «Кто вы в паре?»: вопросы, расчёт, профиль."""

from httpx import AsyncClient

from app.services.otp import MemoryOTPStore
from app.services.personality import PERSONALITY_QUESTIONS, compute_archetype


async def _auth(client, otp_store, phone):
    await client.post("/v1/auth/request-otp", json={"phone": phone})
    code = await otp_store.get_code(phone)
    r = await client.post(
        "/v1/auth/verify-otp",
        json={"phone": phone, "code": code,
              "accepted_documents": ["privacy", "terms"]},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _answers_for(archetype: str) -> list[dict]:
    """Выбрать в каждом вопросе вариант нужного типажа (если есть)."""
    answers = []
    for q in PERSONALITY_QUESTIONS:
        opt = next((o for o in q.options if o.archetype == archetype), q.options[0])
        answers.append({"question_id": q.id, "option_id": opt.id})
    return answers


def test_compute_archetype_unit() -> None:
    answers = {a["question_id"]: a["option_id"] for a in _answers_for("keeper")}
    key, scores = compute_archetype(answers)
    assert key == "keeper"
    assert scores["keeper"] >= max(v for k, v in scores.items() if k != "keeper")


async def test_questions_catalog(client: AsyncClient) -> None:
    meta = (await client.get("/v1/personality/questions")).json()
    assert meta["title"] == "Кто вы в паре?"
    assert "не является" in meta["disclaimer"]
    assert len(meta["questions"]) == 8
    assert all(len(q["options"]) == 4 for q in meta["questions"])


async def test_submit_saves_to_profile(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    headers = await _auth(client, otp_store, "+79996661001")
    resp = await client.post(
        "/v1/personality/submit",
        json={"answers": _answers_for("romantic"), "add_to_profile": True},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["key"] == "romantic"
    assert body["title"] == "Романтик"
    assert len(body["description"]) > 100  # подробное описание
    assert body["in_profile"] is True

    # Типаж виден в анкете и в /result.
    profile = (await client.get("/v1/profile", headers=headers)).json()
    assert profile["personality_archetype"] == "romantic"
    result = (await client.get("/v1/personality/result", headers=headers)).json()
    assert result["key"] == "romantic"


async def test_submit_without_saving(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    headers = await _auth(client, otp_store, "+79996661002")
    resp = await client.post(
        "/v1/personality/submit",
        json={"answers": _answers_for("seeker"), "add_to_profile": False},
        headers=headers,
    )
    assert resp.json()["in_profile"] is False
    assert (
        await client.get("/v1/personality/result", headers=headers)
    ).status_code == 404


async def test_remove_from_profile(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    headers = await _auth(client, otp_store, "+79996661003")
    await client.post(
        "/v1/personality/submit",
        json={"answers": _answers_for("strategist")},
        headers=headers,
    )
    assert (
        await client.delete("/v1/personality/result", headers=headers)
    ).status_code == 204
    assert (
        await client.get("/v1/personality/result", headers=headers)
    ).status_code == 404


async def test_invalid_option_rejected(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    headers = await _auth(client, otp_store, "+79996661004")
    resp = await client.post(
        "/v1/personality/submit",
        json={"answers": [{"question_id": "p1", "option_id": "p2_1"}]},
        headers=headers,
    )
    assert resp.status_code == 400
