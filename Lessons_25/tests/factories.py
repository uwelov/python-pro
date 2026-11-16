"""factory-boy фабрики для тестових даних."""

from __future__ import annotations

from decimal import Decimal

import factory
from django.contrib.auth import get_user_model
from factory.django import DjangoModelFactory

from catalog.models import Book, Category
from orders.models import Order, OrderItem

User = get_user_model()
PASSWORD = "pw12345!"


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    phone_number = factory.Faker("numerify", text="+38067#######")

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        # create_user хешує пароль (у тестах — швидкий MD5, див. settings.TESTING).
        password = kwargs.pop("password", PASSWORD)
        return model_class.objects.create_user(*args, password=password, **kwargs)


class SuperuserFactory(UserFactory):
    username = factory.Sequence(lambda n: f"admin{n}")

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop("password", PASSWORD)
        return model_class.objects.create_superuser(*args, password=password, **kwargs)


class CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.Sequence(lambda n: f"Категорія {n}")
    slug = factory.Sequence(lambda n: f"category-{n}")


class BookFactory(DjangoModelFactory):
    class Meta:
        model = Book

    title = factory.Sequence(lambda n: f"Книга {n}")
    author = factory.Faker("name")
    price = factory.Faker("pydecimal", left_digits=3, right_digits=2, min_value=Decimal("10"), max_value=Decimal("900"))
    description = factory.Faker("sentence")
    stock = 10
    category = factory.SubFactory(CategoryFactory)


class OrderItemFactory(DjangoModelFactory):
    class Meta:
        model = OrderItem

    order = factory.SubFactory("tests.factories.OrderFactory")
    book = factory.SubFactory(BookFactory)
    book_title = factory.LazyAttribute(lambda o: o.book.title)
    price = factory.LazyAttribute(lambda o: o.book.price)
    quantity = 1


class OrderFactory(DjangoModelFactory):
    class Meta:
        model = Order

    user = factory.SubFactory(UserFactory)
    full_name = factory.Faker("name")
    email = factory.Faker("email")
    phone = ""

    @factory.post_generation
    def items(self, create, extracted, **kwargs):
        """OrderFactory(items=[(book, qty), ...]) — створює позиції замовлення."""
        if create and extracted:
            for book, quantity in extracted:
                OrderItemFactory(order=self, book=book, quantity=quantity)
