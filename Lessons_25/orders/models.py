"""Моделі замовлень: Order (шапка замовлення) та OrderItem (рядок замовлення)."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils.translation import gettext, gettext_lazy as _


class Order(models.Model):
    """Замовлення користувача."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Очікує оплати")
        PAID = "paid", _("Оплачено")
        CANCELLED = "cancelled", _("Скасовано")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Користувач"),
        related_name="orders",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    full_name = models.CharField(_("Ім'я та прізвище"), max_length=255)
    email = models.EmailField(_("Електронна пошта"))
    phone = models.CharField(_("Телефон"), max_length=32, blank=True)
    status = models.CharField(
        _("Статус"), max_length=16, choices=Status.choices, default=Status.PENDING
    )
    stripe_session_id = models.CharField(
        "Stripe Checkout Session", max_length=255, blank=True, db_index=True
    )
    stripe_payment_intent_id = models.CharField(
        "Stripe PaymentIntent", max_length=255, blank=True
    )
    created_at = models.DateTimeField(_("Створено"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Оновлено"), auto_now=True)
    paid_at = models.DateTimeField(_("Оплачено"), null=True, blank=True)

    class Meta:
        verbose_name = _("Замовлення")
        verbose_name_plural = _("Замовлення")
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "-created_at"])]

    def __str__(self) -> str:
        return gettext("Замовлення №%(pk)s") % {"pk": self.pk}

    def get_absolute_url(self) -> str:
        return reverse("orders:order-detail", kwargs={"pk": self.pk})

    def get_total_cost(self) -> Decimal:
        """Сума замовлення. Використовує items.all(), тому працює з prefetch_related."""
        return sum((item.get_cost() for item in self.items.all()), Decimal("0"))

    @property
    def is_pending(self) -> bool:
        return self.status == self.Status.PENDING

    @property
    def is_paid(self) -> bool:
        return self.status == self.Status.PAID


class OrderItem(models.Model):
    """Рядок замовлення: книга, кількість та ціна на момент замовлення.

    Назва й ціна копіюються в рядок (snapshot), тому історія замовлень не
    змінюється, якщо книгу пізніше перейменують, подорожчає чи видалять
    (при видаленні книги `book` стає NULL, а `book_title` залишається).
    """

    order = models.ForeignKey(
        Order,
        verbose_name=_("Замовлення"),
        related_name="items",
        on_delete=models.CASCADE,
    )
    book = models.ForeignKey(
        "catalog.Book",
        verbose_name=_("Книга"),
        related_name="order_items",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    book_title = models.CharField(_("Назва на момент замовлення"), max_length=255)
    price = models.DecimalField(_("Ціна за одиницю"), max_digits=8, decimal_places=2)
    quantity = models.PositiveIntegerField(
        _("Кількість"), default=1, validators=[MinValueValidator(1)]
    )

    class Meta:
        verbose_name = _("Позиція замовлення")
        verbose_name_plural = _("Позиції замовлення")
        ordering = ["pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gte=1), name="orderitem_quantity_gte_1"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.book_title} × {self.quantity}"

    def get_cost(self) -> Decimal:
        return self.price * self.quantity
