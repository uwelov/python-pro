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
            Book(
                title="Відьмак",
                author="Анджей Сапковський",
                price="410.00",
                description="Перша книга циклу про відьмака Ґеральта.",
                stock=7,
                category=fantasy,
            ),
            Book(
                title="Герої",
                author="Джо Аберкромбі",
                price="380.00",
                description="Похмуре фентезі про найманців і війну.",
                stock=0,
                category=fantasy,
            ),
            Book(
                title="Зброя, мікроби і сталь",
                author="Джаред Даймонд",
                price="350.00",
                description="Про витоки нерівності між цивілізаціями.",
                stock=4,
                category=history,
            ),
            Book(
                title="Дві Русі",
                author="Ярослав Грицак",
                price="280.00",
                description="Нариси з української історії.",
                stock=6,
                category=history,
            ),
            Book(
                title="Fluent Python",
                author="Luciano Ramalho",
                price="590.00",
                description="Поглиблений посібник з Python.",
                stock=2,
                category=it,
            ),
            Book(
                title="Two Scoops of Django",
                author="Daniel Greenfeld",
                price="470.00",
                description="Найкращі практики розробки на Django.",
                stock=9,
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
