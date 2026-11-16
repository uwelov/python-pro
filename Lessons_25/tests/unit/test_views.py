"""Unit-тести views (Django test client): каталог, CRUD, облік доступу, кошик, акаунти, health."""

from unittest import mock

import pytest
from django.urls import reverse

from catalog.models import Book
from tests.factories import BookFactory, CategoryFactory, OrderFactory

pytestmark = pytest.mark.django_db


# --------------------------------------------------------------- каталог

def test_book_list_ok_and_paginates(client):
    BookFactory.create_batch(8)
    r = client.get(reverse("catalog:book-list"))
    assert r.status_code == 200 and len(r.context["books"]) == 6 and r.context["is_paginated"]
    assert len(client.get(reverse("catalog:book-list"), {"page": 2}).context["books"]) == 2


def test_book_list_filters(client, category):
    other = CategoryFactory()
    BookFactory(title="Дюна", author="Герберт", category=category, stock=3)
    BookFactory(title="Гра", author="Мартін", category=other, stock=0)
    url = reverse("catalog:book-list")
    assert [b.title for b in client.get(url, {"q": "МАРТІН"}).context["books"]] == ["Гра"]  # кирилиця, регістр
    assert [b.title for b in client.get(url, {"category": category.slug}).context["books"]] == ["Дюна"]
    assert [b.title for b in client.get(url, {"stock": "out_of_stock"}).context["books"]] == ["Гра"]
    assert [b.title for b in client.get(url, {"stock": "in_stock"}).context["books"]] == ["Дюна"]


def test_book_list_pagination_keeps_filters(client):
    BookFactory.create_batch(8, author="Той самий")
    r = client.get(reverse("catalog:book-list"), {"q": "Той"})
    assert "q=%D0%A2%D0%BE%D0%B9" in r.context["querystring"]


def test_book_list_empty_state(client):
    assert "Книг за заданими критеріями не знайдено." in client.get(reverse("catalog:book-list")).content.decode()


def test_book_detail_and_404(client, book):
    assert client.get(book.get_absolute_url()).status_code == 200
    assert client.get(reverse("catalog:book-detail", args=[999999])).status_code == 404


def test_category_list_counts(client, category):
    BookFactory.create_batch(3, category=category)
    r = client.get(reverse("catalog:category-list"))
    assert r.context["categories"][0].book_count == 3


# ------------------------------------------------------------- CRUD + права

def test_book_create_requires_login(client):
    r = client.get(reverse("catalog:book-create"))
    assert r.status_code == 302 and "/accounts/login/" in r["Location"]


def test_book_create_forbidden_for_customer(login, customer):
    assert login(customer).get(reverse("catalog:book-create")).status_code == 403


def test_book_create_by_librarian_sets_created_by(login, librarian, category):
    data = {"title": "Нова", "author": "А", "price": "99.90", "description": "", "stock": 4, "category": category.pk}
    r = login(librarian).post(reverse("catalog:book-create"), data)
    book = Book.objects.get(title="Нова")
    assert r.status_code == 302 and book.created_by == librarian


def test_book_update_and_delete_by_librarian(login, librarian, book):
    client = login(librarian)
    data = {"title": "Змінена", "author": book.author, "price": "1.00", "description": "", "stock": 1, "category": book.category_id}
    assert client.post(reverse("catalog:book-update", args=[book.pk]), data).status_code == 302
    book.refresh_from_db()
    assert book.title == "Змінена"
    assert client.post(reverse("catalog:book-delete", args=[book.pk])).status_code == 302
    assert not Book.objects.filter(pk=book.pk).exists()


@pytest.mark.parametrize("name", ["catalog:book-update", "catalog:book-delete"])
def test_update_delete_forbidden_for_customer(login, customer, book, name):
    assert login(customer).get(reverse(name, args=[book.pk])).status_code == 403


def test_book_create_invalid_form_rerenders(login, librarian):
    r = login(librarian).post(reverse("catalog:book-create"), {"title": ""})
    assert r.status_code == 200 and r.context["form"].errors


# ------------------------------------------------------------------ кошик

def test_cart_add_view_and_session(client, book):
    r = client.post(reverse("orders:cart-add", args=[book.pk]), {"quantity": 2})
    assert r.status_code == 302 and client.session["cart"] == {str(book.pk): 2}


def test_cart_add_out_of_stock_and_404(client, book):
    book.stock = 0
    book.save()
    client.post(reverse("orders:cart-add", args=[book.pk]))
    assert "cart" not in client.session
    assert client.post(reverse("orders:cart-add", args=[999999])).status_code == 404


def test_cart_add_invalid_quantity_defaults_to_one(client, book):
    client.post(reverse("orders:cart-add", args=[book.pk]), {"quantity": "abc"})
    assert client.session["cart"] == {str(book.pk): 1}


def test_cart_add_blocks_open_redirect(client, book):
    r = client.post(reverse("orders:cart-add", args=[book.pk]), {"next": "https://evil.example/"})
    assert r["Location"] == reverse("orders:cart-detail")
    r = client.post(reverse("orders:cart-add", args=[book.pk]), {"next": "/categories/"})
    assert r["Location"] == "/categories/"


def test_cart_detail_context(client, book, book2):
    for b, q in ((book, 2), (book2, 1)):
        client.post(reverse("orders:cart-add", args=[b.pk]), {"quantity": q})
    r = client.get(reverse("orders:cart-detail"))
    assert len(r.context["items"]) == 2 and str(r.context["total_price"]) == "1050.50"


def test_cart_remove_clear_and_methods(client, book):
    client.post(reverse("orders:cart-add", args=[book.pk]))
    client.post(reverse("orders:cart-remove", args=[book.pk]))
    assert client.session.get("cart", {}) == {}
    assert client.get(reverse("orders:cart-clear")).status_code == 405


# -------------------------------------------------------- замовлення: доступ

def test_checkout_requires_login_and_nonempty_cart(client, login, user):
    assert client.get(reverse("orders:checkout")).status_code == 302
    r = login(user).get(reverse("orders:checkout"))
    assert r["Location"] == reverse("orders:cart-detail")


def test_order_detail_visible_only_to_owner_or_staff(login, user, other_user, superuser, book):
    order = OrderFactory(user=user, items=[(book, 1)])
    assert login(user).get(order.get_absolute_url()).status_code == 200
    assert login(other_user).get(order.get_absolute_url()).status_code == 404
    assert login(superuser).get(order.get_absolute_url()).status_code == 200


def test_order_list_shows_only_own_orders(login, user, other_user):
    mine, theirs = OrderFactory(user=user), OrderFactory(user=other_user)
    r = login(user).get(reverse("orders:order-list"))
    assert list(r.context["orders"]) == [mine] and theirs not in r.context["orders"]


def test_order_actions_are_post_only_and_owner_only(login, user, other_user, book):
    order = OrderFactory(user=user, items=[(book, 1)])
    assert login(user).get(reverse("orders:order-cancel", args=[order.pk])).status_code == 405
    assert login(other_user).post(reverse("orders:order-cancel", args=[order.pk])).status_code == 404


def test_pay_for_non_pending_order_is_refused(login, user, book, mock_stripe):
    order = OrderFactory(user=user, items=[(book, 1)], status="paid")
    r = login(user).post(reverse("orders:order-pay", args=[order.pk]))
    assert r["Location"] == order.get_absolute_url() and not mock_stripe.create.called


# ----------------------------------------------------------- акаунти, health

def test_register_logs_user_in(client):
    data = {"username": "fresh", "email": "f@e.com", "phone_number": "", "password1": "Str0ng-Pass!42", "password2": "Str0ng-Pass!42"}
    r = client.post(reverse("accounts:register"), data)
    assert r.status_code == 302 and client.session["_auth_user_id"]


def test_login_logout_views(client, user, password):
    assert client.post(reverse("accounts:login"), {"username": user.username, "password": "bad"}).status_code == 200
    assert client.post(reverse("accounts:login"), {"username": user.username, "password": password}).status_code == 302
    assert "_auth_user_id" in client.session
    client.post(reverse("accounts:logout"))
    assert "_auth_user_id" not in client.session
    assert client.get(reverse("accounts:logout")).status_code == 405


def test_health_ok(client):
    r = client.get(reverse("health"))
    assert r.status_code == 200 and r.json() == {"status": "ok", "database": "ok", "cache": "ok"}


def test_health_reports_failures(client):
    with mock.patch("config.health.connection.cursor", side_effect=RuntimeError("db down")):
        r = client.get(reverse("health"))
    assert r.status_code == 503 and r.json()["database"].startswith("error")
    with mock.patch("config.health.cache.set", side_effect=RuntimeError("redis down")):
        assert client.get(reverse("health")).json()["cache"].startswith("error")
