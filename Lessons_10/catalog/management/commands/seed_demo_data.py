"""Заповнення бази тестовими даними (категорії + книги) для демонстрації."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from catalog.models import Book, Category


class Command(BaseCommand):
    help = "Створює тестові категорії та книги для перевірки ORM-запитів."

    def handle(self, *args, **options):
        Book.objects.all().delete()
        Category.objects.all().delete()

        fantasy = Category.objects.create(name="Фантастика", slug="fantasy")
        history = Category.objects.create(name="Історія", slug="history")
        it = Category.objects.create(name="IT та програмування", slug="it")

        books = [
            Book(
                title="Дюна",
                author="Френк Герберт",
                price="450.00",
                description="Класика наукової фантастики про пустельну планету.",
                stock=5,
                category=fantasy,
            ),
            Book(
                title="Гра престолів",
                author="Джордж Мартін",
                price="399.50",
                description="Перша книга саги 'Пісня льоду й полум'я'.",
                stock=0,
                category=fantasy,
            ),
            Book(
                title="Сапієнс",
                author="Юваль Ной Харарі",
                price="320.00",
                description="Коротка історія людства.",
                stock=8,
                category=history,
            ),
            Book(
                title="Кобзар",
                author="Тарас Шевченко",
                price="150.00",
                description="Збірка поезій Тараса Шевченка.",
                stock=12,
                category=history,
            ),
            Book(
                title="Clean Code",
                author="Роберт Мартін",
                price="520.00",
                description="Практики написання чистого коду.",
                stock=3,
                category=it,
            ),
            Book(
                title="Django for Professionals",
                author="William Vincent",
                price="610.00",
                description="Просунутий посібник з Django.",
                stock=0,
                category=it,
            ),
        ]
        Book.objects.bulk_create(books)

        self.stdout.write(
            self.style.SUCCESS(
                f"Створено {Category.objects.count()} категорій та "
                f"{Book.objects.count()} книг."
            )
        )
