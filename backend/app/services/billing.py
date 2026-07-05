"""Биллинг: каталог тарифов, entitlements, активация покупок.

Платёжный провайдер — заглушка (mock): создаёт платёж и возвращает
confirmation_url; подтверждение приходит вебхуком. В prod подключается
ЮKassa/CloudPayments + RuStore-биллинг через тот же интерфейс; фискальный чек
(54-ФЗ) формирует провайдер/ОФД — мы сохраняем receipt_url.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Payment, Profile, Subscription, User

# Каталог: подписки (дают премиум на N дней) и разовые продукты.
PLANS: dict[str, dict] = {
    "premium_1m": {"title": "Премиум · 1 месяц", "price_rub": 499, "days": 30},
    "premium_3m": {"title": "Премиум · 3 месяца", "price_rub": 1190, "days": 90},
}
PRODUCTS: dict[str, dict] = {
    "boost_24h": {"title": "Буст анкеты · 24 часа", "price_rub": 149, "hours": 24},
}

PREMIUM_FEATURES = [
    "who_liked_me",        # список «кто меня лайкнул»
    "extended_limits",     # повышенные лимиты сообщений
    "priority_in_feed",    # приоритет анкеты в подборе
]


def _to_aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def subscription_active(sub: Subscription | None) -> bool:
    return sub is not None and _to_aware(sub.expires_at) > datetime.now(UTC)


async def is_premium(db: AsyncSession, user_id: uuid.UUID) -> bool:
    return subscription_active(await db.get(Subscription, user_id))


def entitlements(premium: bool) -> dict:
    return {
        "premium": premium,
        "features": PREMIUM_FEATURES if premium else [],
        "message_rate_multiplier": 5 if premium else 1,
    }


async def activate_product(db: AsyncSession, user: User, product: str) -> None:
    """Применить оплаченный продукт (вызывается после подтверждения оплаты)."""
    now = datetime.now(UTC)

    if product in PLANS:
        days = PLANS[product]["days"]
        sub = await db.get(Subscription, user.id)
        if sub is None:
            db.add(
                Subscription(
                    user_id=user.id,
                    plan=product,
                    expires_at=now + timedelta(days=days),
                )
            )
        else:
            base = (
                _to_aware(sub.expires_at)
                if subscription_active(sub)
                else now
            )
            sub.plan = product
            sub.expires_at = base + timedelta(days=days)
            sub.auto_renew = True
        return

    if product in PRODUCTS:
        hours = PRODUCTS[product]["hours"]
        profile = await db.get(Profile, user.id)
        if profile is None:
            profile = Profile(user_id=user.id)
            db.add(profile)
        profile.boost_until = now + timedelta(hours=hours)
        return

    raise ValueError(f"unknown product: {product}")


def make_receipt_url(payment: Payment) -> str:
    """Ссылка на фискальный чек (54-ФЗ) — в prod выдаёт провайдер/ОФД."""
    return f"https://receipts.example/{payment.id}"


def price_for(product: str) -> int | None:
    if product in PLANS:
        return PLANS[product]["price_rub"]
    if product in PRODUCTS:
        return PRODUCTS[product]["price_rub"]
    return None
