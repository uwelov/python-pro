"""Інтеграційні тести: наскрізні сценарії користувачів (HTTP + БД + пошта + мок Stripe)."""

import pytest
import stripe
from django.core import mail
from django.urls import reverse

from catalog.models import Book
from orders.models import Order
from tests.factories import BookFactory, CategoryFactory, OrderFactory

pytestmark = pytest.mark.django_db


def add(client, book, qty=1, **extra):
    return client.post(reverse("orders:cart-add", args=[book.pk]), {"quantity": qty, **extra})


def checkout(client, data):
    return client.post(reverse("orders:checkout"), data)


# 1
def test_anonymous_browses_searches_and_opens_detail(client, category):
    dune = BookFactory(title="Дюна", author="Герберт", category=category)
    BookFactory(title="Кобзар", author="Шевченко", category=CategoryFactory())
    assert client.get(reverse("catalog:book-list")).context["paginator"].count == 2
    found = client.get(reverse("catalog:book-list"), {"q": "герберт"}).context["books"]
    assert list(found) == [dune]
    detail = client.get(found[0].get_absolute_url())
    assert detail.status_code == 200 and "Дюна" in detail.content.decode()


# 2
def test_registration_login_state_and_logout(client):
    data = {"username": "ola", "email": "ola@example.com", "phone_number": "", "password1": "Str0ng-Pass!42", "password2": "Str0ng-Pass!42"}
    assert client.post(reverse("accounts:register"), data, follow=True).status_code == 200
    assert "ola" in client.get(reverse("catalog:book-list")).content.decode()
    client.post(reverse("accounts:logout"))
    assert "_auth_user_id" not in client.session


# 3
def test_login_failure_then_success_redirects_to_next(client, user, password):
    url = reverse("accounts:login") + "?next=/orders/"
    assert client.post(url, {"username": user.username, "password": "nope"}).status_code == 200
    r = client.post(url, {"username": user.username, "password": password})
    assert r.status_code == 302 and r["Location"] == "/orders/"


# 4
def test_protected_page_redirects_to_login_and_back(client, user, password, book):
    add(client, book)
    r = client.get(reverse("orders:checkout"))
    assert r.status_code == 302 and "next=/orders/checkout/" in r["Location"]
    r = client.post(r["Location"], {"username": user.username, "password": password})
    assert r["Location"] == "/orders/checkout/"
    assert client.get(r["Location"]).status_code == 200


# 5
def test_cart_lifecycle(client, book, book2):
    add(client, book, 2), add(client, book2, 1)
    assert len(client.get(reverse("orders:cart-detail")).context["cart"]) == 3
    add(client, book, 1, override="1")
    client.post(reverse("orders:cart-remove", args=[book2.pk]))
    assert client.session["cart"] == {str(book.pk): 1}
    client.post(reverse("orders:cart-clear"))
    assert "cart" not in client.session


# 6
def test_guest_cart_survives_login(client, user, password, book):
    add(client, book, 3)
    client.post(reverse("accounts:login"), {"username": user.username, "password": password})
    assert client.session["cart"] == {str(book.pk): 3}


# 7
def test_full_purchase_with_success_page_confirmation(login, user, book, book2, mock_stripe, checkout_data):
    client = login(user)
    add(client, book, 2), add(client, book2, 1)
    r = checkout(client, checkout_data)
    assert r.status_code == 303 and r["Location"].startswith("https://checkout.stripe.com/")
    order = Order.objects.get()
    book.refresh_from_db(), book2.refresh_from_db()
    assert (book.stock, book2.stock) == (3, 1) and "cart" not in client.session
    assert len(mail.outbox) == 1 and mail.outbox[0].to == [checkout_data["email"]]
    r = client.get(reverse("orders:order-success", args=[order.pk]) + "?session_id=cs_test_123")
    order.refresh_from_db()
    assert r.status_code == 302 and order.is_paid and order.stripe_payment_intent_id == "pi_test_1"
    assert "Оплачено" in client.get(reverse("orders:order-list")).content.decode()


# 8
def test_purchase_confirmed_by_webhook_only(login, user, book, mock_stripe, checkout_data, post_webhook):
    client = login(user)
    add(client, book)
    checkout(client, checkout_data)
    order = Order.objects.get()
    assert post_webhook("checkout.session.completed", order.pk).status_code == 200
    order.refresh_from_db()
    assert order.is_paid
    assert post_webhook("checkout.session.completed", order.pk).status_code == 200  # повтор безпечний


# 9
def test_abandoned_payment_expires_and_releases_stock(login, user, book, mock_stripe, checkout_data, post_webhook):
    client = login(user)
    add(client, book, 2)
    checkout(client, checkout_data)
    order = Order.objects.get()
    post_webhook("checkout.session.expired", order.pk, payment_status="unpaid")
    order.refresh_from_db(), book.refresh_from_db()
    assert order.status == Order.Status.CANCELLED and book.stock == 5


# 10
def test_user_cancels_pending_order(login, user, book, mock_stripe, checkout_data):
    client = login(user)
    add(client, book, 2)
    checkout(client, checkout_data)
    order = Order.objects.get()
    client.post(reverse("orders:order-cancel", args=[order.pk]))
    order.refresh_from_db(), book.refresh_from_db()
    assert order.status == "cancelled" and book.stock == 5
    mock_stripe.create.reset_mock()
    client.post(reverse("orders:order-pay", args=[order.pk]))
    assert not mock_stripe.create.called  # скасоване не оплатити


# 11
def test_stripe_failure_then_successful_retry(login, user, book, mock_stripe, checkout_data):
    client = login(user)
    add(client, book, 2)
    mock_stripe.create.side_effect = stripe.APIConnectionError("down")
    assert checkout(client, checkout_data).status_code == 302
    assert Order.objects.get().status == "cancelled" and client.session["cart"] and not mail.outbox
    mock_stripe.create.side_effect = None
    assert checkout(client, checkout_data).status_code == 303
    assert Order.objects.filter(status="pending").count() == 1 and len(mail.outbox) == 1


# 12
def test_retry_payment_for_pending_order(login, user, book, mock_stripe, checkout_data, fake_session):
    client = login(user)
    add(client, book)
    checkout(client, checkout_data)
    order = Order.objects.get()
    mock_stripe.create.return_value = fake_session(id="cs_second", url="https://stripe.test/second")
    r = client.post(reverse("orders:order-pay", args=[order.pk]))
    order.refresh_from_db()
    assert r["Location"] == "https://stripe.test/second" and order.stripe_session_id == "cs_second"


# 13
def test_last_copy_cannot_be_sold_twice(client, django_user_model, mock_stripe, checkout_data, category, password):
    book = BookFactory(category=category, stock=1)
    buyers = [django_user_model.objects.create_user(f"b{i}", f"b{i}@e.com", password) for i in range(2)]
    results = []
    for buyer in buyers:
        client.force_login(buyer)
        add(client, book)
        results.append(checkout(client, checkout_data).status_code)
        client.logout()
    book.refresh_from_db()
    assert results == [303, 302] and book.stock == 0 and Order.objects.count() == 1


# 14
def test_librarian_manages_catalog_and_customer_cannot(login, librarian, customer, category):
    c = login(librarian)
    data = {"title": "Нова", "author": "А", "price": "50.00", "description": "", "stock": 2, "category": category.pk}
    assert c.post(reverse("catalog:book-create"), data).status_code == 302
    book = Book.objects.get()
    assert book.created_by == librarian
    data["title"] = "Оновлена"
    assert c.post(reverse("catalog:book-update", args=[book.pk]), data).status_code == 302
    c.post(reverse("catalog:book-delete", args=[book.pk]))
    assert Book.objects.count() == 0
    book = BookFactory(category=category)
    c = login(customer)
    assert all(c.get(reverse(n, args=a)).status_code == 403 for n, a in (
        ("catalog:book-create", []), ("catalog:book-update", [book.pk]), ("catalog:book-delete", [book.pk])))


# 15
def test_orders_are_private_but_staff_can_see_all(login, user, other_user, superuser, book):
    order = OrderFactory(user=user, items=[(book, 1)])
    assert login(other_user).get(order.get_absolute_url()).status_code == 404
    assert login(superuser).get(order.get_absolute_url()).status_code == 200
    assert order not in login(superuser).get(reverse("orders:order-list")).context["orders"]


# 16
def test_superuser_admin_order_page_with_inline(login, superuser, book, book2):
    order = OrderFactory(items=[(book, 2), (book2, 1)])
    c = login(superuser)
    page = c.get(reverse("admin:orders_order_change", args=[order.pk]))
    assert page.status_code == 200 and "items-TOTAL_FORMS" in page.content.decode()
    assert c.get(reverse("admin:orders_order_changelist"), {"q": order.email}).status_code == 200


# 17
def test_language_switch_changes_catalog_cart_messages_and_email(client, user, book, mock_stripe, checkout_data):
    client.post(reverse("set_language"), {"language": "en", "next": "/"})
    page = client.get(reverse("catalog:book-list")).content.decode()
    assert "Book catalog" in page and '<html lang="en">' in page
    client.force_login(user)
    add(client, book)
    msgs = [str(m) for m in client.get(reverse("orders:cart-detail")).context["messages"]]
    assert any("copy in the cart" in m or "copies in the cart" in m for m in msgs)
    checkout(client, checkout_data)
    assert mail.outbox[0].subject.startswith("Order #")
    client.post(reverse("set_language"), {"language": "uk", "next": "/"})
    assert "Каталог книг" in client.get(reverse("catalog:book-list")).content.decode()


# 18
def test_async_api_flow_matches_catalog(client, login, librarian, category):
    BookFactory(title="Дюна", stock=1, category=category), BookFactory(title="Кобзар", stock=9, category=category)
    listing = client.get(reverse("catalog:api-book-list"), {"q": "дюн"}).json()
    assert listing["count"] == 1
    assert client.get(reverse("catalog:api-book-detail", args=[listing["results"][0]["id"]])).json()["title"] == "Дюна"
    assert client.get(reverse("catalog:api-stats")).json()["books"] == 2
    assert client.get(reverse("catalog:api-low-stock")).status_code == 401
    assert [b["title"] for b in login(librarian).get(reverse("catalog:api-low-stock")).json()["results"]] == ["Дюна"]
