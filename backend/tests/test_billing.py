"""Тесты биллинга: тарифы, оплата, вебхук, премиум-фичи (Стадия 4)."""

from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import get_settings
from app.models import User
from app.services.otp import MemoryOTPStore

SECRET = {"X-Webhook-Secret": get_settings().billing_webhook_secret}


async def _auth(client, otp_store, phone):
    await client.post("/v1/auth/request-otp", json={"phone": phone})
    code = await otp_store.get_code(phone)
    r = await client.post(
        "/v1/auth/verify-otp",
        json={"phone": phone, "code": code,
              "accepted_documents": ["privacy", "terms"]},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _buy(client, headers, product):
    """Полный цикл покупки: checkout + подтверждение вебхуком."""
    co = await client.post(
        "/v1/billing/checkout", json={"product": product}, headers=headers
    )
    assert co.status_code == 201
    pid = co.json()["payment_id"]
    wh = await client.post(
        "/v1/billing/webhook",
        json={"payment_id": pid, "status": "succeeded"},
        headers=SECRET,
    )
    assert wh.status_code == 204
    return pid


async def test_plans_catalog(client: AsyncClient) -> None:
    plans = (await client.get("/v1/billing/plans")).json()
    ids = {p["id"] for p in plans}
    assert "premium_1m" in ids and "boost_24h" in ids
    assert all(p["price_rub"] > 0 for p in plans)


async def test_webhook_rejects_bad_secret(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    headers = await _auth(client, otp_store, "+79995551001")
    co = await client.post(
        "/v1/billing/checkout", json={"product": "premium_1m"}, headers=headers
    )
    resp = await client.post(
        "/v1/billing/webhook",
        json={"payment_id": co.json()["payment_id"], "status": "succeeded"},
        headers={"X-Webhook-Secret": "wrong"},
    )
    assert resp.status_code == 401


async def test_subscription_activation_and_receipt(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    headers = await _auth(client, otp_store, "+79995551002")

    before = (await client.get("/v1/billing/subscription", headers=headers)).json()
    assert before["premium"] is False

    await _buy(client, headers, "premium_1m")

    after = (await client.get("/v1/billing/subscription", headers=headers)).json()
    assert after["premium"] is True
    assert after["plan"] == "premium_1m"
    assert "who_liked_me" in after["features"]

    # Чек (54-ФЗ) сохранён у платежа.
    payments = (await client.get("/v1/billing/payments", headers=headers)).json()
    assert payments[0]["status"] == "paid"
    assert payments[0]["receipt_url"]


async def test_unknown_product_rejected(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    headers = await _auth(client, otp_store, "+79995551003")
    resp = await client.post(
        "/v1/billing/checkout", json={"product": "nope"}, headers=headers
    )
    assert resp.status_code == 400


async def test_liked_me_requires_premium(
    client: AsyncClient, otp_store: MemoryOTPStore, session
) -> None:
    a = await _auth(client, otp_store, "+79995551010")
    b = await _auth(client, otp_store, "+79995551011")
    a_id = (await session.execute(
        select(User).where(User.phone == "+79995551010"))).scalar_one().id
    await client.put(
        "/v1/profile", json={"display_name": "Лайкнувшая"}, headers=b
    )

    # B лайкает A.
    await client.post(
        "/v1/discovery/like", json={"target_user_id": str(a_id)}, headers=b
    )

    # Без премиума — 402.
    resp = await client.get("/v1/discovery/liked-me", headers=a)
    assert resp.status_code == 402
    assert resp.json()["detail"]["error"] == "premium_required"

    # С премиумом — список содержит лайкнувшего.
    await _buy(client, a, "premium_1m")
    resp = await client.get("/v1/discovery/liked-me", headers=a)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_cancel_auto_renew(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    headers = await _auth(client, otp_store, "+79995551020")
    await _buy(client, headers, "premium_1m")

    cancel = await client.post("/v1/billing/cancel", headers=headers)
    assert cancel.status_code == 200
    body = cancel.json()
    assert body["premium"] is True      # действует до конца срока
    assert body["auto_renew"] is False


async def test_boost_purchase_sets_boost(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    headers = await _auth(client, otp_store, "+79995551030")
    await _buy(client, headers, "boost_24h")
    sub = (await client.get("/v1/billing/subscription", headers=headers)).json()
    assert sub["boost_until"] is not None
    assert sub["premium"] is False  # буст не делает премиум


async def test_webhook_idempotent(
    client: AsyncClient, otp_store: MemoryOTPStore
) -> None:
    headers = await _auth(client, otp_store, "+79995551040")
    pid = await _buy(client, headers, "premium_1m")
    # Повторный вебхук не ломает состояние и не продлевает повторно.
    sub1 = (await client.get("/v1/billing/subscription", headers=headers)).json()
    await client.post(
        "/v1/billing/webhook",
        json={"payment_id": pid, "status": "succeeded"},
        headers=SECRET,
    )
    sub2 = (await client.get("/v1/billing/subscription", headers=headers)).json()
    assert sub1["expires_at"] == sub2["expires_at"]
