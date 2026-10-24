"""URLconf застосунку catalog. Підключається з namespace='catalog'."""

from __future__ import annotations

from django.urls import path

from . import views

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
]
