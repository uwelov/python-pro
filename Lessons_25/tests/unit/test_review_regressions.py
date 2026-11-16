"""Тести-відтворювачі знахідок AI code review (див. AI_REVIEW.md).

Кожен тест написано ДО виправлення: на оригінальному коді він падає, після застосування
рекомендацій — проходить. Так кожна прийнята рекомендація підтверджена, а не лише «здається слушною».
"""

from datetime import timedelta
from decimal import Decimal
from unittest import mock

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from catalog.forms import BookFilterForm
from catalog.models import Book
from catalog.views import BookListView
from orders import services
from orders.models import Order
from tests.factories import BookFactory, OrderFactory

pytestmark = pytest.mark.django_db


def add_to_cart(client, book, qty=1):
    client.post(reverse("orders:cart-add", args=[book.pk]), {"quantity": qty})


# --------------------------------------------------------------- CheckoutView

def test_unexpected_error_after_order_creation_releases_stock(client, login, user, book, checkout_data):
    # Generated with AI, reviewed and modified
    client = login(user)
    client.raise_request_exception = False  # хочемо побачити стан БД після 500, а не виняток у тесті
    add_to_cart(client, book, 2)
    with mock.patch("orders.views._redirect_to_stripe", side_effect=RuntimeError("disk full")):
        response = client.post(reverse("orders:checkout"), checkout_data)
    book.refresh_from_db()
    assert response.status_code == 500
    assert Order.objects.get().status == Order.Status.CANCELLED  # інакше замовлення «висить» з резервом
    assert book.stock == 5


def test_stale_pending_orders_are_cancelled_and_stock_released(user, book):
    # Generated with AI, reviewed and modified
    stale = services.create_order(user=user, full_name="A", email="a@b.com", lines=[(book.pk, 2)])
    fresh = services.create_order(user=user, full_name="B", email="b@b.com", lines=[(book.pk, 1)])
    Order.objects.filter(pk=stale.pk).update(created_at=timezone.now() - timedelta(hours=3))

    cancelled = services.cancel_stale_orders(older_than=timedelta(hours=2))

    book.refresh_from_db(), stale.refresh_from_db(), fresh.refresh_from_db()
    assert cancelled == 1 and stale.status == "cancelled" and fresh.status == "pending"
    assert book.stock == 5 - 1  # повернуто лише 2 з простроченого; 1 з свіжого досі зарезервована


def test_stale_cancellation_ignores_paid_orders(user, book):
    # Generated with AI, reviewed and modified
    order = services.create_order(user=user, full_name="A", email="a@b.com", lines=[(book.pk, 1)])
    services.mark_order_paid(order.pk)
    Order.objects.filter(pk=order.pk).update(created_at=timezone.now() - timedelta(days=2))
    assert services.cancel_stale_orders(older_than=timedelta(hours=1)) == 0


def test_cancel_stale_orders_command(user, book, capsys):
    # Generated with AI, reviewed and modified
    order = services.create_order(user=user, full_name="A", email="a@b.com", lines=[(book.pk, 1)])
    Order.objects.filter(pk=order.pk).update(created_at=timezone.now() - timedelta(hours=5))
    call_command("cancel_stale_orders", "--minutes", "60")
    assert "1" in capsys.readouterr().out and Order.objects.get().status == "cancelled"


def test_checkout_form_disables_submit_button_against_double_click(login, user, book):
    # Generated with AI, reviewed and modified
    client = login(user)
    add_to_cart(client, book)
    assert "data-disable-on-submit" in client.get(reverse("orders:checkout")).content.decode()


# -------------------------------------------------------------- stripe_webhook

def test_webhook_with_malformed_order_id_does_not_crash(post_webhook):
    # Generated with AI, reviewed and modified
    response = post_webhook("checkout.session.completed", "not-a-number")
    assert response.status_code == 200  # 500 змусив би Stripe ретраїти подію днями


@pytest.mark.parametrize("amount_total, currency, should_be_paid", [
    (45000, "uah", True),     # збігається із сумою замовлення
    (100, "uah", False),      # сума не збігається
    (45000, "usd", False),    # валюта не збігається
    (None, None, True),       # поля відсутні — перевірку пропускаємо (зворотна сумісність)
])
def test_webhook_verifies_amount_and_currency(post_webhook, user, book, amount_total, currency, should_be_paid):
    # Generated with AI, reviewed and modified
    order = OrderFactory(user=user, items=[(book, 1)])  # 450.00 грн = 45000 «копійок»
    fields = {} if amount_total is None else {"amount_total": amount_total, "currency": currency}
    assert post_webhook("checkout.session.completed", order.pk, **fields).status_code == 200
    order.refresh_from_db()
    assert order.is_paid is should_be_paid


def test_success_page_does_not_trust_mismatched_amount(login, user, book, mock_stripe, fake_session):
    # Generated with AI, reviewed and modified
    order = OrderFactory(user=user, items=[(book, 1)], stripe_session_id="cs_test_123")
    mock_stripe.retrieve.return_value = fake_session(payment_status="paid", payment_intent="pi_1",
                                                     amount_total=1, currency="uah")
    login(user).get(reverse("orders:order-success", args=[order.pk]) + "?session_id=cs_test_123")
    order.refresh_from_db()
    assert order.status == Order.Status.PENDING


# ---------------------------------------------------------------- BookListView

def test_book_list_queryset_has_deterministic_ordering(rf):
    # Generated with AI, reviewed and modified
    view = BookListView()
    view.request = rf.get("/")
    sql = str(view.get_queryset().query)
    assert 'ORDER BY "catalog_book"."title" ASC, "catalog_book"."id" ASC' in sql


def test_book_list_sanitizes_unknown_filter_values(client):
    # Generated with AI, reviewed and modified
    BookFactory.create_batch(2)
    response = client.get(reverse("catalog:book-list"), {"stock": "banana", "q": "   "})
    assert len(response.context["books"]) == 2
    assert response.context["current_stock"] == "" and response.context["current_query"] == ""


@pytest.mark.parametrize("params, expected", [
    ({"q": "  дюна  "}, {"q": "дюна", "category": "", "stock": ""}),
    ({"stock": "in_stock"}, {"q": "", "category": "", "stock": "in_stock"}),
    ({"stock": "banana"}, {"q": "", "category": "", "stock": ""}),
    ({}, {"q": "", "category": "", "stock": ""}),
])
def test_book_filter_form_cleaning(params, expected):
    # Generated with AI, reviewed and modified
    assert BookFilterForm(params).cleaned_values() == expected


def test_book_filter_form_filters_queryset(category):
    # Generated with AI, reviewed and modified
    BookFactory(title="Дюна", author="Герберт", category=category, stock=2)
    BookFactory(title="Гра", author="Мартін", category=category, stock=0)
    form = BookFilterForm({"q": "МАРТІН", "stock": "out_of_stock", "category": category.slug})
    assert [b.title for b in form.filter(Book.objects.all())] == ["Гра"]
    assert Decimal("0") == 0  # нагадування: фільтр не чіпає ціни
