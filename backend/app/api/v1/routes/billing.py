"""Биллинг: тарифы, оплата, вебхук провайдера, подписка."""

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models import Payment, Profile, Subscription, User
from app.models.billing import PaymentStatus
from app.schemas.billing import (
    CheckoutIn,
    CheckoutOut,
    PaymentOut,
    PlanOut,
    SubscriptionOut,
    WebhookIn,
)
from app.services.analytics import track_event
from app.services.audit import write_audit
from app.services.billing import (
    PLANS,
    PRODUCTS,
    activate_product,
    entitlements,
    make_receipt_url,
    price_for,
    subscription_active,
)

router = APIRouter(prefix="/billing", tags=["billing"])
settings = get_settings()


@router.get("/plans", response_model=list[PlanOut])
async def list_plans() -> list[PlanOut]:
    """Каталог тарифов и разовых продуктов."""
    plans = [
        PlanOut(id=k, title=v["title"], price_rub=v["price_rub"], kind="plan")
        for k, v in PLANS.items()
    ]
    products = [
        PlanOut(id=k, title=v["title"], price_rub=v["price_rub"], kind="product")
        for k, v in PRODUCTS.items()
    ]
    return plans + products


@router.post("/checkout", response_model=CheckoutOut, status_code=201)
async def checkout(
    data: CheckoutIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CheckoutOut:
    """Создать платёж; оплата подтверждается вебхуком провайдера."""
    amount = price_for(data.product)
    if amount is None:
        raise HTTPException(status_code=400, detail="unknown product")

    payment = Payment(user_id=user.id, product=data.product, amount_rub=amount)
    db.add(payment)
    await db.commit()
    await db.refresh(payment)

    track_event(
        "checkout_created",
        {"user_id": str(user.id), "product": data.product, "amount": amount},
    )
    # В prod: URL подтверждения от ЮKassa/CloudPayments.
    return CheckoutOut(
        payment_id=payment.id,
        confirmation_url=f"https://pay.example/confirm/{payment.id}",
        amount_rub=amount,
    )


@router.post("/webhook", status_code=204)
async def provider_webhook(
    data: WebhookIn,
    db: AsyncSession = Depends(get_db),
    x_webhook_secret: str = Header(default=""),
) -> None:
    """Callback провайдера (в prod — криптоподпись; здесь — общий секрет)."""
    if x_webhook_secret != settings.billing_webhook_secret:
        raise HTTPException(status_code=401, detail="invalid webhook signature")

    payment = await db.get(Payment, data.payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="payment not found")
    if payment.status != PaymentStatus.pending:
        return  # идемпотентность: повторный вебхук игнорируем

    if data.status == "succeeded":
        payment.status = PaymentStatus.paid
        payment.receipt_url = make_receipt_url(payment)
        user = await db.get(User, payment.user_id)
        if user is not None:
            await activate_product(db, user, payment.product)
        write_audit(db, None, "payment_paid", str(payment.id))
        track_event(
            "payment_succeeded",
            {"user_id": str(payment.user_id), "product": payment.product},
        )
    else:
        payment.status = PaymentStatus.failed
        track_event("payment_failed", {"payment_id": str(payment.id)})

    await db.commit()


@router.get("/subscription", response_model=SubscriptionOut)
async def my_subscription(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionOut:
    sub = await db.get(Subscription, user.id)
    premium = subscription_active(sub)
    ent = entitlements(premium)
    profile = await db.get(Profile, user.id)
    return SubscriptionOut(
        premium=premium,
        plan=sub.plan if premium and sub else None,
        expires_at=sub.expires_at if premium and sub else None,
        auto_renew=sub.auto_renew if premium and sub else False,
        features=ent["features"],
        boost_until=profile.boost_until if profile else None,
    )


@router.post("/cancel", response_model=SubscriptionOut)
async def cancel_auto_renew(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionOut:
    """Отключить автопродление; подписка действует до конца оплаченного срока."""
    sub = await db.get(Subscription, user.id)
    if sub is None or not subscription_active(sub):
        raise HTTPException(status_code=404, detail="no active subscription")
    sub.auto_renew = False
    await db.commit()
    track_event("subscription_cancelled", {"user_id": str(user.id)})
    return await my_subscription(user, db)


@router.get("/payments", response_model=list[PaymentOut])
async def my_payments(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PaymentOut]:
    rows = (
        await db.execute(
            select(Payment)
            .where(Payment.user_id == user.id)
            .order_by(desc(Payment.created_at))
        )
    ).scalars().all()
    return [
        PaymentOut(
            id=p.id,
            product=p.product,
            amount_rub=p.amount_rub,
            status=p.status.value,
            receipt_url=p.receipt_url,
            created_at=p.created_at,
        )
        for p in rows
    ]
