"""URLconf застосунку catalog. Підключається з namespace='catalog'."""

from __future__ import annotations

from django.urls import path

from . import async_views, views

app_name = "catalog"

urlpatterns = [
    path("", views.BookListView.as_view(), name="book-list"),
    path("books/add/", views.BookCreateView.as_view(), name="book-create"),
    path("books/<int:pk>/", views.BookDetailView.as_view(), name="book-detail"),
    path(
        "books/<int:pk>/edit/", views.BookUpdateView.as_view(), name="book-update"
    ),
    path(
        "books/<int:pk>/delete/",
        views.BookDeleteView.as_view(),
        name="book-delete",
    ),
    path("categories/", views.CategoryListView.as_view(), name="category-list"),
    # Асинхронний JSON API (async def + async ORM)
    path("api/books/", async_views.book_list_api, name="api-book-list"),
    path("api/books/<int:pk>/", async_views.book_detail_api, name="api-book-detail"),
    path("api/categories/", async_views.category_list_api, name="api-category-list"),
    path("api/stats/", async_views.stats_api, name="api-stats"),
    path("api/low-stock/", async_views.low_stock_api, name="api-low-stock"),
]
