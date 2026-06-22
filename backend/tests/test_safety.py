"""Тесты верификации, жалоб, блокировок и аудита."""

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


async def test_selfie_verification_success(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    headers = await _auth(client, otp_store, "+79990000020")
    files = {"file": ("selfie.jpg", b"live selfie", "image/jpeg")}
    resp = await client.post("/v1/verify/selfie", files=files, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    assert resp.json()["is_verified"] is True

    # Бейдж отражается в анкете.
    profile = await client.get("/v1/profile", headers=headers)
    assert profile.json()["is_verified"] is True


async def test_selfie_verification_failure(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    headers = await _auth(client, otp_store, "+79990000021")
    files = {"file": ("fail.jpg", b"fail liveness", "image/jpeg")}
    resp = await client.post("/v1/verify/selfie", files=files, headers=headers)
    assert resp.json()["status"] == "rejected"
    assert resp.json()["is_verified"] is False


async def test_report_and_block_flow(
    client: AsyncClient, otp_store: MemoryOTPStore, session
) -> None:
    a_headers = await _auth(client, otp_store, "+79990000022")
    await _auth(client, otp_store, "+79990000023")
    target = (
        await session.execute(select(User).where(User.phone == "+79990000023"))
    ).scalar_one()

    # Жалоба
    resp = await client.post(
        "/v1/reports",
        json={"target_user_id": str(target.id), "reason": "спам"},
        headers=a_headers,
    )
    assert resp.status_code == 201

    # Блокировка (идемпотентна)
    for _ in range(2):
        b = await client.post(
            "/v1/blocks", json={"target_user_id": str(target.id)}, headers=a_headers
        )
        assert b.status_code == 204

    blocks = await client.get("/v1/blocks", headers=a_headers)
    assert str(target.id) in blocks.json()
    assert len(blocks.json()) == 1

    # Разблокировка
    un = await client.delete(f"/v1/blocks/{target.id}", headers=a_headers)
    assert un.status_code == 204


async def test_cannot_report_self(
    client: AsyncClient, otp_store: MemoryOTPStore, session
) -> None:
    headers = await _auth(client, otp_store, "+79990000024")
    me = (
        await session.execute(select(User).where(User.phone == "+79990000024"))
    ).scalar_one()
    resp = await client.post(
        "/v1/reports",
        json={"target_user_id": str(me.id), "reason": "x"},
        headers=headers,
    )
    assert resp.status_code == 400


async def test_audit_log_records_actions(
    client: AsyncClient, otp_store: MemoryOTPStore, session
) -> None:
    headers = await _auth(client, otp_store, "+79990000025")
    files = {"file": ("selfie.jpg", b"live", "image/jpeg")}
    await client.post("/v1/verify/selfie", files=files, headers=headers)

    # Назначаем модератора и читаем аудит.
    mod_headers = await _auth(client, otp_store, "+79990000026")
    mod = (
        await session.execute(select(User).where(User.phone == "+79990000026"))
    ).scalar_one()
    mod.role = UserRole.moderator
    await session.commit()

    audit = await client.get("/v1/moderation/audit", headers=mod_headers)
    assert audit.status_code == 200
    actions = {row["action"] for row in audit.json()}
    assert "verification_selfie" in actions
