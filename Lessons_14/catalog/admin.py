"""Налаштування адмін-панелі для каталогу книг."""

from __future__ import annotations

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from .models import Book, Category


class BookInline(admin.TabularInline):
    """Інлайн-редагування книг прямо на сторінці категорії."""

    model = Book
    extra = 1
    fields = ("title", "author", "price", "stock")
    show_change_link = True


class StockStatusFilter(admin.SimpleListFilter):
    """Власний фільтр: книги в наявності / відсутні на складі."""

    title = "наявність на складі"
    parameter_name = "stock_status"

    def lookups(self, request: HttpRequest, model_admin: admin.ModelAdmin):
        return (
            ("in_stock", "В наявності"),
            ("out_of_stock", "Немає в наявності"),
        )

    def queryset(self, request: HttpRequest, queryset: QuerySet) -> QuerySet:
        if self.value() == "in_stock":
            return queryset.filter(stock__gt=0)
        if self.value() == "out_of_stock":
            return queryset.filter(stock=0)
        return queryset


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Адмінка категорій з інлайном книг усередині категорії."""

    list_display = ("name", "slug", "book_count")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [BookInline]

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        # Одразу рахуємо кількість книг у кожній категорії (annotate),
        # щоб не робити зайвий запит для кожного рядка списку.
        from django.db.models import Count

        return super().get_queryset(request).annotate(_book_count=Count("books"))

    @admin.display(description="Кількість книг", ordering="_book_count")
    def book_count(self, obj: Category) -> int:
        return obj._book_count


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    """Адмінка книг: список, фільтри, пошук."""

    list_display = ("title", "author", "category", "price", "stock", "in_stock")
    list_filter = ("category", StockStatusFilter)
    search_fields = ("title", "author", "description")
    list_select_related = ("category",)
    autocomplete_fields = ("category",)
    list_editable = ("price", "stock")
    ordering = ("title",)

    @admin.display(description="В наявності", boolean=True)
    def in_stock(self, obj: Book) -> bool:
        return obj.in_stock
