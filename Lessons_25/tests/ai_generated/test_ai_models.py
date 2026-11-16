"""Тести моделей Category, Book та Order/OrderItem, згенеровані за допомогою AI.

Процес описано в AI_REVIEW.md (розділ «Генерація тестів»): чернетка від Claude -> запуск ->
ревʼю -> правки -> мутаційна перевірка. У кожному тесті є коментар
`# Generated with AI, reviewed and modified` (це перевіряє останній тест файла).
"""

import ast
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone, translation

from catalog.models import Book, Category
from orders.models import Order, OrderItem
from tests.factories import BookFactory, CategoryFactory, OrderFactory, OrderItemFactory, UserFactory

pytestmark = pytest.mark.django_db


def new_book(category, **overrides):
    """Незбережена книга з валідними значеннями за замовчуванням."""
    data = dict(title="Дюна", author="Френк Герберт", price=Decimal("450.00"), stock=5, category=category)
    return Book(**{**data, **overrides})


# ====================================================================== Category

def test_category_str_returns_name():
    # Generated with AI, reviewed and modified
    assert str(CategoryFactory(name="Фантастика")) == "Фантастика"


@pytest.mark.parametrize("slug", ["fantasy", "sci-fi", "history_2", "a"])
def test_category_valid_slugs(slug):
    # Generated with AI, reviewed and modified
    Category(name=f"n-{slug}", slug=slug).full_clean()


def test_category_slug_rejects_cyrillic():
    # Generated with AI, reviewed and modified
    # SlugField за замовчуванням allow_unicode=False — слаг для URL має бути ASCII.
    with pytest.raises(ValidationError) as exc:
        Category(name="Фантастика", slug="фантастика").full_clean()
    assert "slug" in exc.value.message_dict


@pytest.mark.parametrize("slug", ["bad slug", "bad/slug", "bad.slug", ""])
def test_category_invalid_slugs(slug):
    # Generated with AI, reviewed and modified
    with pytest.raises(ValidationError) as exc:
        Category(name="x", slug=slug).full_clean()
    assert "slug" in exc.value.message_dict


def test_category_name_and_slug_must_be_unique():
    # Generated with AI, reviewed and modified
    CategoryFactory(name="Історія", slug="history")
    with pytest.raises(ValidationError) as exc:
        Category(name="Історія", slug="history").full_clean()
    assert set(exc.value.message_dict) == {"name", "slug"}


def test_category_name_max_length_is_100():
    # Generated with AI, reviewed and modified
    Category(name="а" * 100, slug="ok").full_clean()
    with pytest.raises(ValidationError):
        Category(name="а" * 101, slug="ok").full_clean()


def test_categories_are_ordered_by_name():
    # Generated with AI, reviewed and modified
    for name in ("Фантастика", "Історія", "IT"):
        CategoryFactory(name=name)
    assert list(Category.objects.values_list("name", flat=True)) == sorted(["Фантастика", "Історія", "IT"])


def test_category_books_reverse_relation():
    # Generated with AI, reviewed and modified
    category = CategoryFactory()
    BookFactory.create_batch(3, category=category)
    BookFactory()  # книга з іншої категорії
    assert category.books.count() == 3


@pytest.mark.parametrize("lang, singular, plural", [("uk", "Категорія", "Категорії"), ("en", "Category", "Categories")])
def test_category_verbose_names_by_language(lang, singular, plural):
    # Generated with AI, reviewed and modified
    with translation.override(lang):
        assert (str(Category._meta.verbose_name), str(Category._meta.verbose_name_plural)) == (singular, plural)


# ========================================================================== Book

def test_book_str_and_absolute_url(category):
    # Generated with AI, reviewed and modified
    book = BookFactory(title="Кобзар", author="Тарас Шевченко", category=category)
    assert str(book) == "Кобзар (Тарас Шевченко)" and book.get_absolute_url() == f"/books/{book.pk}/"


@pytest.mark.parametrize("stock, expected", [(0, False), (1, True), (2, True), (10_000, True)])
def test_book_in_stock_boundaries(category, stock, expected):
    # Generated with AI, reviewed and modified
    assert new_book(category, stock=stock).in_stock is expected


@pytest.mark.parametrize("price", ["0.00", "0.01", "999999.99", "450"])
def test_book_valid_prices(category, price):
    # Generated with AI, reviewed and modified
    new_book(category, price=Decimal(price)).full_clean()


@pytest.mark.parametrize("price, reason", [
    ("-0.01", "від'ємна ціна"),
    ("1000000.00", "понад 8 цифр (max_digits=8)"),
    ("1.234", "понад 2 знаки після коми (decimal_places=2)"),
])
def test_book_invalid_prices(category, price, reason):
    # Generated with AI, reviewed and modified
    with pytest.raises(ValidationError) as exc:
        new_book(category, price=Decimal(price)).full_clean()
    assert "price" in exc.value.message_dict, reason


def test_book_negative_price_is_rejected_by_database_too(category):
    # Generated with AI, reviewed and modified
    # Знайдено ревʼю цього тесту: валідатор не спрацьовує при .save(), тому потрібен CheckConstraint у БД.
    with pytest.raises(IntegrityError), transaction.atomic():
        Book.objects.create(title="x", author="y", price=Decimal("-1"), stock=1, category=category)


def test_book_negative_stock_is_rejected(category):
    # Generated with AI, reviewed and modified
    with pytest.raises(ValidationError) as exc:
        new_book(category, stock=-1).full_clean()
    assert "stock" in exc.value.message_dict
    with pytest.raises(IntegrityError), transaction.atomic():
        Book.objects.create(title="x", author="y", price=1, stock=-1, category=category)


def test_book_required_fields(category):
    # Generated with AI, reviewed and modified
    with pytest.raises(ValidationError) as exc:
        Book(price=Decimal("1"), stock=1).full_clean()
    assert {"title", "author", "category"} <= set(exc.value.message_dict)
    new_book(category, description="").full_clean()  # опис необов'язковий


def test_book_title_and_author_max_length_is_255(category):
    # Generated with AI, reviewed and modified
    new_book(category, title="я" * 255, author="я" * 255).full_clean()
    with pytest.raises(ValidationError):
        new_book(category, title="я" * 256).full_clean()


def test_books_are_ordered_by_title():
    # Generated with AI, reviewed and modified
    for title in ("Я", "А", "Б"):
        BookFactory(title=title)
    assert list(Book.objects.values_list("title", flat=True)) == ["А", "Б", "Я"]


def test_book_created_at_is_set_once():
    # Generated with AI, reviewed and modified
    book = BookFactory()
    created = book.created_at
    book.title = "Змінено"
    book.save()
    book.refresh_from_db()
    assert created is not None and book.created_at == created


def test_book_relations_and_delete_behaviour():
    # Generated with AI, reviewed and modified
    user = UserFactory()
    book = BookFactory(created_by=user)
    assert list(user.books_added.all()) == [book]
    user.delete()
    book.refresh_from_db()
    assert book.created_by is None  # SET_NULL: книга лишається
    book.category.delete()
    assert not Book.objects.filter(pk=book.pk).exists()  # CASCADE: книги зникають разом з категорією


def test_book_labels_by_language():
    # Generated with AI, reviewed and modified
    with translation.override("en"):
        assert Book._meta.get_field("stock").verbose_name == "Stock quantity"
        assert str(Book._meta.verbose_name) == "Book"
    with translation.override("uk"):
        assert Book._meta.get_field("stock").verbose_name == "Кількість на складі"


# ================================================================ Order / OrderItem

def test_order_status_choices_and_default():
    # Generated with AI, reviewed and modified
    assert {value for value, _ in Order.Status.choices} == {"pending", "paid", "cancelled"}
    order = OrderFactory()
    assert order.status == Order.Status.PENDING and order.paid_at is None and order.stripe_session_id == ""


@pytest.mark.parametrize("status, pending, paid", [("pending", True, False), ("paid", False, True), ("cancelled", False, False)])
def test_order_status_properties(status, pending, paid):
    # Generated with AI, reviewed and modified
    order = Order(status=status)
    assert (order.is_pending, order.is_paid) == (pending, paid)


def test_order_validation_rejects_bad_status_and_email():
    # Generated with AI, reviewed and modified
    with pytest.raises(ValidationError) as exc:
        Order(full_name="A", email="not-an-email", status="refunded").full_clean()
    assert {"email", "status"} <= set(exc.value.message_dict)
    Order(full_name="A", email="a@b.com", phone="").full_clean(exclude=["user"])  # телефон необов'язковий


def test_order_total_cost(category):
    # Generated with AI, reviewed and modified
    cheap = BookFactory(category=category, price=Decimal("0.10"))
    dear = BookFactory(category=category, price=Decimal("999.99"))
    order = OrderFactory(items=[(cheap, 3), (dear, 2)])
    assert order.get_total_cost() == Decimal("0.30") + Decimal("1999.98")  # без похибок float


def test_order_total_cost_of_empty_order_is_zero():
    # Generated with AI, reviewed and modified
    assert OrderFactory().get_total_cost() == Decimal("0")


def test_order_total_cost_uses_prefetched_items(book, django_assert_num_queries):
    # Generated with AI, reviewed and modified
    OrderFactory(items=[(book, 1), (book, 2)])
    order = Order.objects.prefetch_related("items").get()
    with django_assert_num_queries(0):  # позиції вже в пам'яті — додаткових запитів немає
        assert order.get_total_cost() == book.price * 3


def test_orders_are_listed_newest_first():
    # Generated with AI, reviewed and modified
    old, new = OrderFactory(), OrderFactory()
    Order.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=1))
    assert list(Order.objects.all()) == [new, old]


def test_order_has_status_index():
    # Generated with AI, reviewed and modified
    assert any(index.fields == ["status", "-created_at"] for index in Order._meta.indexes)


def test_order_str_and_url_by_language():
    # Generated with AI, reviewed and modified
    order = OrderFactory()
    assert order.get_absolute_url() == f"/orders/{order.pk}/"
    with translation.override("en"):
        assert str(order) == f"Order #{order.pk}"
    with translation.override("uk"):
        assert str(order) == f"Замовлення №{order.pk}"


def test_order_item_cost_is_exact(book):
    # Generated with AI, reviewed and modified
    item = OrderItemFactory(book=book, price=Decimal("0.10"), quantity=3)
    assert item.get_cost() == Decimal("0.30") and str(item) == f"{book.title} × 3"


@pytest.mark.parametrize("quantity", [0, -1])
def test_order_item_quantity_must_be_positive_in_validation(book, quantity):
    # Generated with AI, reviewed and modified
    item = OrderItem(order=OrderFactory(), book=book, book_title="x", price=Decimal("1"), quantity=quantity)
    with pytest.raises(ValidationError) as exc:
        item.full_clean()
    assert "quantity" in exc.value.message_dict


def test_order_item_zero_quantity_is_rejected_by_database(book):
    # Generated with AI, reviewed and modified
    # Валідатори не спрацьовують при .save() — нуль відсікає CheckConstraint orderitem_quantity_gte_1.
    with pytest.raises(IntegrityError), transaction.atomic():
        OrderItem.objects.create(order=OrderFactory(), book=book, book_title="x", price=Decimal("1"), quantity=0)


def test_order_item_keeps_snapshot_after_book_changes_or_is_deleted(book):
    # Generated with AI, reviewed and modified
    item = OrderItemFactory(book=book, quantity=2)
    snapshot_price, snapshot_title = item.price, item.book_title
    book.price, book.title = Decimal("1.00"), "Нова назва"
    book.save()
    item.refresh_from_db()
    assert (item.price, item.book_title) == (snapshot_price, snapshot_title)
    book.delete()
    item.refresh_from_db()
    assert item.book is None and item.book_title == snapshot_title


def test_order_relations_cascade_and_set_null():
    # Generated with AI, reviewed and modified
    user = UserFactory()
    order = OrderFactory(user=user, items=[(BookFactory(), 1)])
    assert list(user.orders.all()) == [order]
    user.delete()
    order.refresh_from_db()
    assert order.user is None and order.items.count() == 1  # замовлення переживає видалення акаунта
    order.delete()
    assert OrderItem.objects.count() == 0  # позиції видаляються разом із замовленням


def test_order_items_keep_insertion_order():
    # Generated with AI, reviewed and modified
    order = OrderFactory()
    first = OrderItemFactory(order=order, book_title="перша")
    second = OrderItemFactory(order=order, book_title="друга")
    assert list(order.items.all()) == [first, second]


# ======================================================== мета-перевірка коментарів

def test_every_test_in_this_file_has_the_ai_comment():
    # Generated with AI, reviewed and modified
    source = Path(__file__).read_text(encoding="utf-8")
    missing = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            body = "\n".join(source.split("\n")[node.lineno - 1: node.end_lineno])
            if "# Generated with AI, reviewed and modified" not in body:
                missing.append(node.name)
    assert missing == []
