"""Unit-тести сервісного шару: create_order / cancel_order / mark_order_paid, платежі, email."""

from decimal import Decimal
from unittest import mock

import pytest
import stripe
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.utils import translation

from orders import emails, payments, services
from orders.models import Order
from tests.conftest import WEBHOOK_SECRET, sign
from tests.factories import OrderFactory

pytestmark = pytest.mark.django_db


def create(user, lines, **kw):
    return services.create_order(user=user, full_name="Іван", email="ivan@example.com", lines=lines, **kw)


def test_create_order_reserves_stock_and_snapshots(user, book, book2):
    order = create(user, [(book.pk, 2), (book2.pk, 1)])
    book.refresh_from_db(), book2.refresh_from_db()
    assert (book.stock, book2.stock) == (3, 1)
    assert order.get_total_cost() == Decimal("1050.50") and order.status == Order.Status.PENDING


def test_create_order_rolls_back_on_insufficient_stock(user, book, book2):
    with pytest.raises(services.InsufficientStockError) as exc:
        create(user, [(book.pk, 1), (book2.pk, 99)])
    assert exc.value.available == 2 and Order.objects.count() == 0
    book.refresh_from_db()
    assert book.stock == 5


def test_create_order_rejects_empty_and_missing_book(user):
    with pytest.raises(services.EmptyOrderError):
        create(user, [])
    with pytest.raises(services.InsufficientStockError):
        create(user, [(999999, 1)])


def test_insufficient_stock_message_is_translated(user, book):
    with translation.override("en"), pytest.raises(services.InsufficientStockError) as exc:
        create(user, [(book.pk, 50)])
    assert "50 ordered, 5 in stock" in str(exc.value)


def test_email_deferred_until_commit(user, book, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        create(user, [(book.pk, 1)])
    assert len(callbacks) == 1 and len(mail.outbox) == 0
    callbacks[0]()
    assert len(mail.outbox) == 1


def test_notify_false_skips_email(user, book, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        create(user, [(book.pk, 1)], notify=False)
    assert mail.outbox == []


def test_cancel_order_restores_stock_once(user, book):
    order = create(user, [(book.pk, 3)])
    assert services.cancel_order(order.pk) is True and services.cancel_order(order.pk) is False
    book.refresh_from_db()
    assert book.stock == 5


def test_cancel_skips_deleted_books(user, book):
    order = create(user, [(book.pk, 1)])
    book.delete()
    assert services.cancel_order(order.pk) is True


def test_mark_paid_is_idempotent_and_final(user, book):
    order = create(user, [(book.pk, 1)])
    assert services.mark_order_paid(order.pk, session_id="cs_1", payment_intent_id="pi_1") is True
    assert services.mark_order_paid(order.pk) is False and services.cancel_order(order.pk) is False
    order.refresh_from_db()
    assert order.is_paid and order.paid_at and order.stripe_payment_intent_id == "pi_1"


def test_payment_for_cancelled_order_is_not_resurrected(user, book):
    order = create(user, [(book.pk, 1)])
    services.cancel_order(order.pk)
    assert services.mark_order_paid(order.pk) is False
    order.refresh_from_db()
    assert order.status == Order.Status.CANCELLED


# ------------------------------------------------------------------ payments

@pytest.mark.parametrize("amount, currency, expected", [
    (Decimal("450.00"), "uah", 45000), (Decimal("0.005"), "usd", 1), (Decimal("19.99"), "EUR", 1999),
    (Decimal("500"), "jpy", 500),
])
def test_to_minor_units(amount, currency, expected):
    assert payments.to_minor_units(amount, currency) == expected


def test_create_checkout_session_parameters(book, mock_stripe):
    order = OrderFactory(items=[(book, 2)], email="x@y.com")
    payments.create_checkout_session(order, success_url="http://t/s?session_id={CHECKOUT_SESSION_ID}", cancel_url="http://t/c")
    kw = mock_stripe.create.call_args.kwargs
    assert kw["mode"] == "payment" and kw["customer_email"] == "x@y.com"
    assert kw["line_items"][0]["quantity"] == 2 and kw["line_items"][0]["price_data"]["unit_amount"] == 45000
    assert kw["metadata"] == {"order_id": str(order.pk)} and kw["expires_at"] > 0


def test_missing_secret_key_raises(settings, book):
    settings.STRIPE_SECRET_KEY = ""
    with pytest.raises(ImproperlyConfigured):
        payments.create_checkout_session(OrderFactory(items=[(book, 1)]), success_url="u", cancel_url="c")


def test_retrieve_session_delegates_to_stripe(mock_stripe):
    assert payments.retrieve_session("cs_x").payment_status == "paid"
    mock_stripe.retrieve.assert_called_once_with("cs_x")


def test_webhook_signature_verification():
    payload = '{"id":"evt_1","object":"event","type":"ping","data":{"object":{}}}'
    assert payments.construct_webhook_event(payload.encode(), sign(payload))["type"] == "ping"
    with pytest.raises(stripe.SignatureVerificationError):
        payments.construct_webhook_event(payload.encode(), sign(payload, secret="whsec_other"))
    with pytest.raises(ValueError):
        payments.construct_webhook_event(b"not json", sign("not json"))


# --------------------------------------------------------------------- email

@pytest.mark.parametrize("lang, subject_part, body_part", [("en", "Order #", "Total:"), ("uk", "Замовлення №", "Разом:")])
def test_order_email_language(book, lang, subject_part, body_part):
    order = OrderFactory(items=[(book, 1)], email="buyer@example.com")
    with translation.override(lang):
        assert emails.send_order_created_email(order.pk) is True
    message = mail.outbox[0]
    assert message.to == ["buyer@example.com"] and subject_part in message.subject
    assert body_part in message.body and message.alternatives[0].mimetype == "text/html"


def test_order_email_failure_is_swallowed(book):
    order = OrderFactory(items=[(book, 1)])
    with mock.patch("django.core.mail.EmailMultiAlternatives.send", side_effect=OSError("smtp down")):
        assert emails.send_order_created_email(order.pk) is False


def test_order_email_for_missing_order_returns_false(db):
    assert emails.send_order_created_email(424242) is False
