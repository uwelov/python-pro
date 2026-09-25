"""Моделі каталогу книгарні: категорії книг та самі книги."""

from __future__ import annotations

from django.db import models


class Category(models.Model):
    """Категорія книг (наприклад, "Фантастика", "Історія")."""

    name = models.CharField("Назва", max_length=100, unique=True)
    slug = models.SlugField(
        "Слаг",
        max_length=120,
        unique=True,
        help_text="Унікальний ідентифікатор для URL, напр. 'fantasy'",
    )

    class Meta:
        verbose_name = "Категорія"
        verbose_name_plural = "Категорії"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Book(models.Model):
    """Книга, що продається в магазині."""

    title = models.CharField("Назва", max_length=255)
    author = models.CharField("Автор", max_length=255)
    price = models.DecimalField("Ціна", max_digits=8, decimal_places=2)
    description = models.TextField("Опис", blank=True)
    stock = models.PositiveIntegerField(
        "Кількість на складі", default=0
    )
    category = models.ForeignKey(
        Category,
        verbose_name="Категорія",
        related_name="books",
        on_delete=models.CASCADE,
    )
    created_at = models.DateTimeField("Дата додавання", auto_now_add=True)

    class Meta:
        verbose_name = "Книга"
        verbose_name_plural = "Книги"
        ordering = ["title"]

    def __str__(self) -> str:
        return f"{self.title} ({self.author})"

    @property
    def in_stock(self) -> bool:
        """Чи є книга в наявності."""
        return self.stock > 0
