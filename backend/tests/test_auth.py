"""Тесты регистрации по OTP, JWT и согласий."""

from httpx import AsyncClient

from app.services.otp import MemoryOTPStore

PHONE = "+79991234567"


async def _get_tokens(client: AsyncClient, otp_store: MemoryOTPStore) -> dict:
    resp = await client.post("/v1/auth/request-otp", json={"phone": PHONE})
    assert resp.status_code == 200
    code = await otp_store.get_code(PHONE)
    assert code is not None
    resp = await client.post(
        "/v1/auth/verify-otp", json={"phone": PHONE, "code": code}
    )
    assert resp.status_code == 200
    return resp.json()


async def test_request_otp_invalid_phone(client: AsyncClient) -> None:
    resp = await client.post("/v1/auth/request-otp", json={"phone": "abc"})
    assert resp.status_code == 422


async def test_register_new_user_via_otp(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    tokens = await _get_tokens(client, otp_store)
    assert tokens["is_new_user"] is True
    assert tokens["access_token"]
    assert tokens["refresh_token"]


async def test_verify_wrong_code(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    await client.post("/v1/auth/request-otp", json={"phone": PHONE})
    resp = await client.post(
        "/v1/auth/verify-otp", json={"phone": PHONE, "code": "000000"}
    )
    assert resp.status_code == 400


async def test_existing_user_not_marked_new(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    first = await _get_tokens(client, otp_store)
    assert first["is_new_user"] is True
    second = await _get_tokens(client, otp_store)
    assert second["is_new_user"] is False


async def test_refresh_token(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    tokens = await _get_tokens(client, otp_store)
    resp = await client.post(
        "/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]


async def test_refresh_rejects_access_token(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    tokens = await _get_tokens(client, otp_store)
    resp = await client.post(
        "/v1/auth/refresh", json={"refresh_token": tokens["access_token"]}
    )
    assert resp.status_code == 401


async def test_consent_requires_auth(client: AsyncClient) -> None:
    resp = await client.post(
        "/v1/consents", json={"doc_type": "privacy", "doc_version": "1.0"}
    )
    assert resp.status_code == 401


async def test_accept_and_list_consent(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    tokens = await _get_tokens(client, otp_store)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    resp = await client.post(
        "/v1/consents",
        json={"doc_type": "privacy", "doc_version": "1.0"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["doc_type"] == "privacy"

    resp = await client.get("/v1/consents", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
