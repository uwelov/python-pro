"""Адмінка замовлень: Order з inline-позиціями OrderItem."""

from __future__ import annotations

from decimal import Decimal

from django.contrib import admin
from django.db.models import DecimalField, ExpressionWrapper, F, QuerySet, Sum
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    """Позиції замовлення прямо на сторінці замовлення."""

    model = OrderItem
    extra = 0
    autocomplete_fields = ("book",)  # працює завдяки search_fields у BookAdmin
    fields = ("book", "book_title", "price", "quantity", "cost")
    readonly_fields = ("cost",)

    @admin.display(description=_("Сума"))
    def cost(self, obj: OrderItem) -> Decimal | str:
        return obj.get_cost() if obj.pk else "—"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "email", "status", "total_cost", "created_at", "paid_at")
    list_filter = ("status", "created_at")
    list_select_related = ("user",)
    search_fields = ("id", "email", "full_name", "phone", "user__username", "stripe_session_id")
    date_hierarchy = "created_at"
    inlines = [OrderItemInline]
    readonly_fields = (
        "total_cost",
        "stripe_session_id",
        "stripe_payment_intent_id",
        "created_at",
        "updated_at",
        "paid_at",
    )
    fieldsets = (
        (_("Клієнт"), {"fields": ("user", "full_name", "email", "phone")}),
        (_("Замовлення"), {"fields": ("status", "total_cost", "created_at", "updated_at", "paid_at")}),
        ("Stripe", {"fields": ("stripe_session_id", "stripe_payment_intent_id")}),
    )

    def get_queryset(self, request: HttpRequest) -> QuerySet[Order]:
        # Сума рахується в БД одним запитом (а не окремо для кожного рядка списку).
        return super().get_queryset(request).annotate(
            _total=Sum(
                ExpressionWrapper(
                    F("items__price") * F("items__quantity"),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            )
        )

    @admin.display(description=_("Сума, грн"), ordering="_total")
    def total_cost(self, obj: Order) -> Decimal:
        total = getattr(obj, "_total", None)
        if total is None:
            total = obj.get_total_cost()
        return Decimal(total).quantize(Decimal("0.01"))  # завжди дві цифри після коми
