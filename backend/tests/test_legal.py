"""Тесты юр-документов и переподтверждения согласий (Этап C)."""

from httpx import AsyncClient

from app.core.config import get_settings
from app.services.otp import MemoryOTPStore


async def _reg(client, otp_store, phone):
    await client.post("/v1/auth/request-otp", json={"phone": phone})
    code = await otp_store.get_code(phone)
    r = await client.post(
        "/v1/auth/verify-otp",
        json={"phone": phone, "code": code,
              "accepted_documents": ["privacy", "terms"]},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_document_text_and_404(client: AsyncClient) -> None:
    ok = await client.get("/v1/legal/documents/privacy")
    assert ok.status_code == 200
    assert "152-ФЗ" in ok.json()["text"]
    assert (await client.get("/v1/legal/documents/nope")).status_code == 404


async def test_pending_empty_after_registration(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    headers = await _reg(client, otp_store, "+79998880001")
    resp = await client.get("/v1/legal/pending", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_reconsent_required_on_version_bump(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    headers = await _reg(client, otp_store, "+79998880002")
    settings = get_settings()
    orig = settings.consent_privacy_version
    try:
        settings.consent_privacy_version = "2.0"  # выпущена новая версия
        pending = await client.get("/v1/legal/pending", headers=headers)
        assert pending.json() == ["privacy"]

        # Подбор блокируется до переподтверждения.
        disc = await client.get("/v1/discovery", headers=headers)
        assert disc.status_code == 403
        assert disc.json()["detail"]["error"] == "reconsent_required"

        # Переподтверждаем — список пуст.
        rc = await client.post(
            "/v1/legal/reconsent",
            json={"accepted_documents": ["privacy"]},
            headers=headers,
        )
        assert rc.json() == []
    finally:
        settings.consent_privacy_version = orig
