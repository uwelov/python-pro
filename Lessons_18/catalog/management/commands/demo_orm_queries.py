"""
Демонстрація Django ORM-запитів: filter, annotate, Q-об'єкти.

Запуск (спочатку створити тестові дані):
    python manage.py seed_demo_data
    python manage.py demo_orm_queries
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db.models import Avg, Count, Q

from catalog.models import Book, Category


class Command(BaseCommand):
    help = "Виводить приклади ORM-запитів (filter, annotate, Q) у консоль."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("\n1. filter() — книги в наявності дешевші за 500"))
        cheap_in_stock = Book.objects.filter(stock__gt=0, price__lt=500)
        for book in cheap_in_stock:
            self.stdout.write(f"  - {book.title} ({book.price} грн, залишок {book.stock})")

        self.stdout.write(self.style.MIGRATE_HEADING("\n2. filter() — книги певної категорії за slug"))
        it_books = Book.objects.filter(category__slug="it")
        for book in it_books:
            self.stdout.write(f"  - {book.title}")

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "\n3. Q-об'єкти — пошук за назвою АБО автором (регістронезалежно)"
            )
        )
        query = "мартін"
        search_results = Book.objects.filter(
            Q(title__icontains=query) | Q(author__icontains=query)
        )
        for book in search_results:
            self.stdout.write(f"  - {book.title} — {book.author}")

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "\n4. Q-об'єкти — книги в наявності, окрім категорії 'Історія'"
            )
        )
        filtered = Book.objects.filter(Q(stock__gt=0) & ~Q(category__slug="history"))
        for book in filtered:
            self.stdout.write(f"  - {book.title} ({book.category.name})")

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "\n5. annotate() — кількість книг та середня ціна в кожній категорії"
            )
        )
        categories = Category.objects.annotate(
            book_count=Count("books"), avg_price=Avg("books__price")
        )
        for category in categories:
            avg_price = f"{category.avg_price:.2f}" if category.avg_price else "—"
            self.stdout.write(
                f"  - {category.name}: {category.book_count} книг, "
                f"середня ціна {avg_price} грн"
            )

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "\n6. annotate() + filter() — категорії, де є хоча б одна відсутня книга"
            )
        )
        categories_with_out_of_stock = Category.objects.annotate(
            out_of_stock_count=Count("books", filter=Q(books__stock=0))
        ).filter(out_of_stock_count__gt=0)
        for category in categories_with_out_of_stock:
            self.stdout.write(
                f"  - {category.name}: {category.out_of_stock_count} книг(и) відсутні"
            )

        self.stdout.write(self.style.SUCCESS("\nГотово."))
