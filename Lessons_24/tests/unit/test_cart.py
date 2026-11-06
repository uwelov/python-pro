"""Unit-тести класу Cart (кошик у сесії)."""

from decimal import Decimal

import pytest
from django.contrib.sessions.backends.cache import SessionStore
from django.test import RequestFactory

from orders.cart import Cart

pytestmark = pytest.mark.django_db


@pytest.fixture
def cart():
    request = RequestFactory().get("/")
    request.session = SessionStore()
    return Cart(request)


def test_new_cart_is_empty(cart):
    assert len(cart) == 0 and list(cart) == [] and cart.get_total_price() == Decimal("0")


def test_add_accumulates(cart, book):
    cart.add(book, 2)
    assert cart.add(book, 1) == 3 and len(cart) == 3


def test_add_is_clamped_to_stock(cart, book2):
    assert cart.add(book2, 99) == 2


def test_override_replaces(cart, book):
    cart.add(book, 4)
    assert cart.add(book, 1, override_quantity=True) == 1


def test_zero_or_out_of_stock_removes(cart, book):
    cart.add(book, 2)
    assert cart.add(book, 0, override_quantity=True) == 0 and len(cart) == 0
    book.stock = 0
    assert cart.add(book, 1) == 0


def test_remove_and_clear(cart, book, book2):
    cart.add(book), cart.add(book2)
    cart.remove(book)
    assert cart.lines() == [(book2.pk, 1)]
    cart.remove(book)  # повторне видалення безпечне
    cart.clear()
    assert len(cart) == 0 and "cart" not in cart.session


def test_iteration_and_totals(cart, book, book2):
    cart.add(book, 2), cart.add(book2, 1)
    items = list(cart)
    assert {i["book"].pk: i["total_price"] for i in items} == {book.pk: Decimal("900.00"), book2.pk: Decimal("150.50")}
    assert cart.get_total_price() == Decimal("1050.50")


def test_over_stock_flag(cart, book):
    cart.add(book, 5)
    book.stock = 2
    book.save()
    assert list(cart)[0]["over_stock"] is True


def test_deleted_books_are_dropped(cart, book):
    cart.add(book)
    book.delete()
    assert list(cart) == [] and len(cart) == 0


def test_cart_persists_in_session(book):
    request = RequestFactory().get("/")
    request.session = SessionStore()
    Cart(request).add(book, 2)
    assert Cart(request).lines() == [(book.pk, 2)]
