"""Асинхронні JSON API-views каталогу (async def + async ORM).

Що тут показано:
    * `async for` по QuerySet і `acount()` / `aget()` / `aaggregate()` — асинхронний ORM;
    * `asyncio.gather()` — кілька запитів до БД «одночасно» в одному view;
    * `await request.auser()` / `await user.ahas_perm()` — асинхронна автентифікація.

Важливо: у async-коді не можна звертатися до лінивих зв'язків (book.category) чи
`request.user` напряму — це синхронний доступ до БД і Django кине
SynchronousOnlyOperation. Тому `select_related()` та `await request.auser()`.

Під WSGI (gunicorn) такі view теж працюють, але виконуються в окремому потоці; повноцінно
async-режим вмикається під ASGI-сервером (uvicorn) — саме так запускається Docker-образ.
"""

from __future__ import annotations

import asyncio

from django.db.models import Avg, Count, Max, Min, Q, Sum
from django.http import HttpRequest, JsonResponse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET

from .models import Book, Category

MAX_LIMIT = 50
LOW_STOCK_THRESHOLD = 3


def json_response(data, status: int = 200) -> JsonResponse:
    """JsonResponse, що не екранує кирилицю (\\u0414 -> Д) і приймає не лише dict."""
    return JsonResponse(
        data, status=status, safe=False, json_dumps_params={"ensure_ascii": False}
    )


def serialize_book(book: Book) -> dict:
    """Книга -> dict. Потребує book.category, завантаженого через select_related."""
    return {
        "id": book.pk,
        "title": book.title,
        "author": book.author,
        "price": str(book.price),
        "stock": book.stock,
        "in_stock": book.in_stock,
        "category": {"id": book.category_id, "name": book.category.name, "slug": book.category.slug},
    }


@require_GET
async def book_list_api(request: HttpRequest):
    """GET /api/books/?q=&category=&limit= — пошук книг (асинхронний ORM)."""
    queryset = Book.objects.select_related("category")

    query = request.GET.get("q", "").strip()
    if query:
        queryset = queryset.filter(Q(title__icontains=query) | Q(author__icontains=query))
    category = request.GET.get("category", "").strip()
    if category:
        queryset = queryset.filter(category__slug=category)

    try:
        limit = min(max(int(request.GET.get("limit", 10)), 1), MAX_LIMIT)
    except ValueError:
        limit = 10

    # Два незалежні запити виконуємо «одночасно».
    total, results = await asyncio.gather(
        queryset.acount(),
        _collect(queryset[:limit]),
    )
    return json_response({"count": total, "results": results})


async def _collect(queryset) -> list[dict]:
    return [serialize_book(book) async for book in queryset]


@require_GET
async def book_detail_api(request: HttpRequest, pk: int):
    """GET /api/books/<pk>/ — одна книга (`aget`)."""
    try:
        book = await Book.objects.select_related("category").aget(pk=pk)
    except Book.DoesNotExist:
        return json_response({"error": _("Книгу не знайдено.")}, status=404)
    return json_response(serialize_book(book))


@require_GET
async def category_list_api(request: HttpRequest):
    """GET /api/categories/ — категорії з кількістю книг (annotate + async for)."""
    queryset = Category.objects.annotate(book_count=Count("books")).order_by("name")
    data = [
        {"id": c.pk, "name": c.name, "slug": c.slug, "book_count": c.book_count}
        async for c in queryset
    ]
    return json_response(data)


@require_GET
async def stats_api(request: HttpRequest):
    """GET /api/stats/ — зведена статистика: кілька запитів паралельно через gather."""
    books_total, in_stock, categories, prices = await asyncio.gather(
        Book.objects.acount(),
        Book.objects.filter(stock__gt=0).acount(),
        Category.objects.acount(),
        Book.objects.aaggregate(
            avg=Avg("price"), min=Min("price"), max=Max("price"), units=Sum("stock")
        ),
    )

    def money(value):
        return None if value is None else str(round(value, 2))

    return json_response(
        {
            "books": books_total,
            "books_in_stock": in_stock,
            "books_out_of_stock": books_total - in_stock,
            "categories": categories,
            "units_in_stock": prices["units"] or 0,
            "price": {"avg": money(prices["avg"]), "min": money(prices["min"]), "max": money(prices["max"])},
        }
    )


@require_GET
async def low_stock_api(request: HttpRequest):
    """GET /api/low-stock/ — книги, що закінчуються. Лише для користувачів з правом change_book."""
    user = await request.auser()  # асинхронний аналог request.user
    if not user.is_authenticated:
        return json_response({"error": _("Потрібна автентифікація.")}, status=401)
    if not await user.ahas_perm("catalog.change_book"):
        return json_response({"error": _("Недостатньо прав.")}, status=403)

    queryset = Book.objects.select_related("category").filter(stock__lte=LOW_STOCK_THRESHOLD).order_by("stock", "title")
    return json_response(
        {"threshold": LOW_STOCK_THRESHOLD, "results": [serialize_book(b) async for b in queryset]}
    )
