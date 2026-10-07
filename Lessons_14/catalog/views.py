"""Class-Based Views каталогу книгарні."""

from __future__ import annotations

from django.contrib import messages
from django.db.models import Count, Q, QuerySet
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .forms import BookForm
from .models import Book, Category


class BookListView(ListView):
    """Список книг із пошуком, фільтрами за категорією/наявністю та пагінацією."""

    model = Book
    paginate_by = 6
    context_object_name = "books"

    def get_queryset(self) -> QuerySet[Book]:
        queryset = Book.objects.select_related("category").all()

        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) | Q(author__icontains=query)
            )

        category_slug = self.request.GET.get("category", "").strip()
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)

        stock_status = self.request.GET.get("stock", "").strip()
        if stock_status == "in_stock":
            queryset = queryset.filter(stock__gt=0)
        elif stock_status == "out_of_stock":
            queryset = queryset.filter(stock=0)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.annotate(book_count=Count("books"))
        context["current_query"] = self.request.GET.get("q", "")
        context["current_category"] = self.request.GET.get("category", "")
        context["current_stock"] = self.request.GET.get("stock", "")

        # querystring без 'page' — щоб пагінація зберігала активні фільтри
        params = self.request.GET.copy()
        params.pop("page", None)
        context["querystring"] = params.urlencode()
        return context


class BookDetailView(DetailView):
    """Детальна сторінка книги."""

    model = Book
    context_object_name = "book"
    queryset = Book.objects.select_related("category")


class BookCreateView(CreateView):
    """Додавання нової книги."""

    model = Book
    form_class = BookForm

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Книгу «{self.object.title}» додано.")
        return response


class BookUpdateView(UpdateView):
    """Редагування існуючої книги."""

    model = Book
    form_class = BookForm

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Книгу «{self.object.title}» оновлено.")
        return response


class BookDeleteView(DeleteView):
    """Видалення книги з підтвердженням."""

    model = Book
    success_url = reverse_lazy("catalog:book-list")

    def form_valid(self, form):
        title = self.object.title
        response = super().form_valid(form)
        messages.success(self.request, f"Книгу «{title}» видалено.")
        return response


class CategoryListView(ListView):
    """Список категорій з кількістю книг у кожній (для навігації/фільтрів)."""

    model = Category
    context_object_name = "categories"

    def get_queryset(self) -> QuerySet[Category]:
        return Category.objects.annotate(book_count=Count("books"))
