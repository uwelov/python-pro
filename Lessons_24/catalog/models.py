"""Моделі каталогу книгарні: категорії книг та самі книги."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


class Category(models.Model):
    """Категорія книг (наприклад, "Фантастика", "Історія")."""

    name = models.CharField(_("Назва"), max_length=100, unique=True)
    slug = models.SlugField(
        _("Слаг"),
        max_length=120,
        unique=True,
        help_text=_("Унікальний ідентифікатор для URL, напр. 'fantasy'"),
    )

    class Meta:
        verbose_name = _("Категорія")
        verbose_name_plural = _("Категорії")
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Book(models.Model):
    """Книга, що продається в магазині."""

    title = models.CharField(_("Назва"), max_length=255)
    author = models.CharField(_("Автор"), max_length=255)
    price = models.DecimalField(_("Ціна"), max_digits=8, decimal_places=2)
    description = models.TextField(_("Опис"), blank=True)
    stock = models.PositiveIntegerField(
        _("Кількість на складі"), default=0
    )
    category = models.ForeignKey(
        Category,
        verbose_name=_("Категорія"),
        related_name="books",
        on_delete=models.CASCADE,
    )
    created_at = models.DateTimeField(_("Дата додавання"), auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Додав(-ла)"),
        related_name="books_added",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text=_("Користувач, який додав цей запис (якщо акаунт видалено — поле очищається)."),
    )

    class Meta:
        verbose_name = _("Книга")
        verbose_name_plural = _("Книги")
        ordering = ["title"]

    def __str__(self) -> str:
        return f"{self.title} ({self.author})"

    @property
    def in_stock(self) -> bool:
        """Чи є книга в наявності."""
        return self.stock > 0

    def get_absolute_url(self) -> str:
        return reverse("catalog:book-detail", kwargs={"pk": self.pk})
