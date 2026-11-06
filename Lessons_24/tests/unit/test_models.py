"""Unit-тести моделей: Category, Book, User, Order, OrderItem."""

from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import translation

from accounts.models import User
from catalog.models import Book, Category
from orders.models import Order, OrderItem
from tests.factories import BookFactory, CategoryFactory, OrderFactory, OrderItemFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_category_str_and_ordering():
    CategoryFactory(name="Б"), CategoryFactory(name="А")
    assert [str(c) for c in Category.objects.all()] == ["А", "Б"]


def test_category_slug_is_unique():
    CategoryFactory(slug="same")
    with pytest.raises(IntegrityError), transaction.atomic():
        CategoryFactory(slug="same")


def test_book_str_and_url(book):
    assert str(book) == "Дюна (Френк Герберт)"
    assert book.get_absolute_url() == f"/books/{book.pk}/"


@pytest.mark.parametrize("stock, expected", [(0, False), (1, True), (50, True)])
def test_book_in_stock(stock, expected):
    assert BookFactory(stock=stock).in_stock is expected


def test_books_are_ordered_by_title():
    BookFactory(title="Я"), BookFactory(title="А")
    assert [b.title for b in Book.objects.all()] == ["А", "Я"]


def test_deleting_category_cascades_to_books(book, category):
    category.delete()
    assert not Book.objects.filter(pk=book.pk).exists()


def test_book_created_by_is_set_null_when_user_deleted(user):
    book = BookFactory(created_by=user)
    user.delete()
    book.refresh_from_db()
    assert book.created_by is None


def test_custom_user_model():
    user = UserFactory(phone_number="")
    assert User._meta.label == "accounts.User"
    assert str(user) == user.username and user.phone_number == ""


def test_order_defaults_and_helpers(book):
    order = OrderFactory(items=[(book, 1)])
    assert order.status == Order.Status.PENDING and order.is_pending and not order.is_paid
    assert order.get_absolute_url() == f"/orders/{order.pk}/"
    assert str(order) == f"Замовлення №{order.pk}"


def test_order_total_cost_sums_items(book, book2):
    order = OrderFactory(items=[(book, 2), (book2, 1)])
    assert order.get_total_cost() == Decimal("1050.50")


def test_order_item_cost_and_str(book):
    item = OrderItemFactory(book=book, quantity=3)
    assert item.get_cost() == Decimal("1350.00") and str(item) == "Дюна × 3"


def test_order_item_quantity_must_be_positive(book):
    with pytest.raises(IntegrityError), transaction.atomic():
        OrderItem.objects.create(order=OrderFactory(), book=book, book_title="x", price=1, quantity=0)


def test_order_item_survives_book_deletion(book):
    item = OrderItemFactory(book=book)
    book.delete()
    item.refresh_from_db()
    assert item.book is None and item.book_title == "Дюна"


def test_order_cascade_deletes_items(book):
    order = OrderFactory(items=[(book, 1)])
    order.delete()
    assert OrderItem.objects.count() == 0


def test_order_user_set_null_on_user_delete():
    order = OrderFactory()
    order.user.delete()
    order.refresh_from_db()
    assert order.user is None


@pytest.mark.parametrize("lang, label", [("uk", "Очікує оплати"), ("en", "Awaiting payment")])
def test_order_status_label_is_translated(lang, label):
    with translation.override(lang):
        assert Order.Status.PENDING.label == label


def test_model_verbose_names_are_translated():
    with translation.override("en"):
        assert Book._meta.get_field("price").verbose_name == "Price"
        assert str(Book._meta.verbose_name_plural) == "Books"
    with translation.override("uk"):
        assert Book._meta.get_field("price").verbose_name == "Ціна"
