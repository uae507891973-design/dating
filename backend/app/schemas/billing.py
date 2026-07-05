"""Схемы биллинга."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class PlanOut(BaseModel):
    id: str
    title: str
    price_rub: int
    kind: str  # plan | product


class CheckoutIn(BaseModel):
    product: str


class CheckoutOut(BaseModel):
    payment_id: uuid.UUID
    confirmation_url: str
    amount_rub: int


class WebhookIn(BaseModel):
    payment_id: uuid.UUID
    status: str  # succeeded | failed


class SubscriptionOut(BaseModel):
    premium: bool
    plan: str | None = None
    expires_at: datetime | None = None
    auto_renew: bool = False
    features: list[str] = []
    boost_until: datetime | None = None


class PaymentOut(BaseModel):
    id: uuid.UUID
    product: str
    amount_rub: int
    status: str
    receipt_url: str | None
    created_at: datetime
