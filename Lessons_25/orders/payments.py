"""Інтеграція зі Stripe Checkout (hosted-сторінка оплати).

Потік оплати:
    1. створюємо Order (status=pending) і резервуємо книги;
    2. `create_checkout_session()` -> Stripe повертає session.url;
    3. редірект клієнта на session.url (оплата на боці Stripe);
    4. Stripe повертає клієнта на success_url і одночасно шле вебхук
       `checkout.session.completed` — за будь-яким із двох каналів
       замовлення позначається оплаченим (див. services.mark_order_paid).
"""

from __future__ import annotations

import time
from decimal import ROUND_HALF_UP, Decimal

import stripe
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .models import Order

# Валюти без копійок: сума передається цілим числом як є (решта — у мінорних одиницях, ×100).
ZERO_DECIMAL_CURRENCIES = frozenset(
    {"bif", "clp", "djf", "gnf", "jpy", "kmf", "krw", "mga", "pyg", "rwf",
     "ugx", "vnd", "vuv", "xaf", "xof", "xpf"}
)


def to_minor_units(amount: Decimal, currency: str) -> int:
    """450.00 (uah) -> 45000; 450 (jpy) -> 450."""
    if currency.lower() in ZERO_DECIMAL_CURRENCIES:
        return int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _configure() -> None:
    if not settings.STRIPE_SECRET_KEY:
        raise ImproperlyConfigured(
            "STRIPE_SECRET_KEY не задано. Додайте тестовий ключ (sk_test_...) у .env."
        )
    stripe.api_key = settings.STRIPE_SECRET_KEY


def create_checkout_session(order: Order, *, success_url: str, cancel_url: str):
    """Створює Stripe Checkout Session для замовлення.

    `success_url` має містити `{CHECKOUT_SESSION_ID}` — Stripe підставить id сесії.
    """
    _configure()
    currency = settings.STRIPE_CURRENCY

    line_items = [
        {
            "quantity": item.quantity,
            "price_data": {
                "currency": currency,
                "unit_amount": to_minor_units(item.price, currency),
                "product_data": {"name": item.book_title},
            },
        }
        for item in order.items.all()
    ]

    return stripe.checkout.Session.create(
        mode="payment",
        line_items=line_items,
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=str(order.pk),
        customer_email=order.email,
        metadata={"order_id": str(order.pk)},
        payment_intent_data={"metadata": {"order_id": str(order.pk)}},
        expires_at=int(time.time()) + settings.STRIPE_SESSION_TTL,
    )


def retrieve_session(session_id: str):
    """Отримує сесію зі Stripe (для перевірки статусу оплати на сторінці успіху)."""
    _configure()
    return stripe.checkout.Session.retrieve(session_id)


def construct_webhook_event(payload: bytes, signature_header: str):
    """Перевіряє підпис вебхука й повертає подію.

    Raises:
        ValueError: некоректний JSON.
        stripe.SignatureVerificationError: підпис не збігається з STRIPE_WEBHOOK_SECRET.
    """
    return stripe.Webhook.construct_event(
        payload, signature_header, settings.STRIPE_WEBHOOK_SECRET
    )
