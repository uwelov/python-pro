"""Спільні фікстури pytest."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

import factory.random
import pytest
from django.contrib.auth.models import Group
from django.utils import translation
from django.core.management import call_command
from django.urls import reverse

from .factories import (
    PASSWORD, BookFactory, CategoryFactory, OrderFactory, SuperuserFactory, UserFactory,
)

WEBHOOK_SECRET = "whsec_test_secret"


@pytest.fixture(autouse=True)
def _deterministic_and_stripe_settings(settings):
    factory.random.reseed_random(1234)
    settings.STRIPE_SECRET_KEY = "sk_test_dummy"
    settings.STRIPE_WEBHOOK_SECRET = WEBHOOK_SECRET
    settings.STRIPE_CURRENCY = "uah"


@pytest.fixture(autouse=True)
def _reset_language(settings):
    """LocaleMiddleware активує мову в потоці й не скидає її — не даємо мові «протікати» між тестами."""
    translation.activate(settings.LANGUAGE_CODE)
    yield
    translation.activate(settings.LANGUAGE_CODE)


@pytest.fixture
def password():
    return PASSWORD


@pytest.fixture
def groups(db):
    call_command("setup_groups", verbosity=0)


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def other_user(db):
    return UserFactory()


@pytest.fixture
def customer(groups):
    u = UserFactory()
    u.groups.add(Group.objects.get(name="Клієнти"))
    return u


@pytest.fixture
def librarian(groups):
    u = UserFactory()
    u.groups.add(Group.objects.get(name="Бібліотекарі"))
    return u


@pytest.fixture
def superuser(db):
    return SuperuserFactory()


@pytest.fixture
def category(db):
    return CategoryFactory()


@pytest.fixture
def book(category):
    return BookFactory(category=category, stock=5, price=Decimal("450.00"), title="Дюна", author="Френк Герберт")


@pytest.fixture
def book2(category):
    return BookFactory(category=category, stock=2, price=Decimal("150.50"), title="Кобзар", author="Тарас Шевченко")


@pytest.fixture
def login(client):
    """login(user) — авторизує тестовий клієнт без форми логіну."""
    def _login(u):
        client.force_login(u)
        return client
    return _login


@pytest.fixture
def make_order(db):
    return OrderFactory


# ---------------------------------------------------------------- Stripe (мок)

@pytest.fixture
def fake_session():
    def _make(**overrides):
        data = dict(id="cs_test_123", url="https://checkout.stripe.com/pay/cs_test_123",
                    payment_status="unpaid", payment_intent=None)
        data.update(overrides)
        return SimpleNamespace(**data)
    return _make


@pytest.fixture
def mock_stripe(fake_session):
    """Мокає зовнішні виклики Stripe: створення та отримання Checkout Session."""
    with mock.patch("orders.payments.stripe.checkout.Session.create", return_value=fake_session()) as create, \
         mock.patch("orders.payments.stripe.checkout.Session.retrieve") as retrieve:
        retrieve.return_value = fake_session(payment_status="paid", payment_intent="pi_test_1")
        yield SimpleNamespace(create=create, retrieve=retrieve)


def sign(payload: str, secret: str = WEBHOOK_SECRET) -> str:
    """Справжній заголовок Stripe-Signature (t=...,v1=HMAC-SHA256)."""
    ts = int(time.time())
    digest = hmac.new(secret.encode(), f"{ts}.{payload}".encode(), hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"


@pytest.fixture
def post_webhook(client):
    def _post(event_type, order, *, signature=None, **fields):
        obj = {"id": "cs_test_123", "object": "checkout.session", "payment_status": "paid",
               "payment_intent": "pi_test_1", "client_reference_id": str(order),
               "metadata": {"order_id": str(order)}, **fields}
        payload = json.dumps({"id": "evt_1", "object": "event", "type": event_type, "data": {"object": obj}})
        return client.post(reverse("orders:stripe-webhook"), payload, content_type="application/json",
                           HTTP_STRIPE_SIGNATURE=signature or sign(payload))
    return _post


@pytest.fixture
def checkout_data():
    return {"full_name": "Іван Тест", "email": "ivan@example.com", "phone": "+380501112233"}
