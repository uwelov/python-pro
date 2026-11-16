"""Class-Based Views каталогу книгарні."""

from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Count, QuerySet
from django.urls import reverse_lazy
from django.utils.functional import cached_property
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)
from django.utils.translation import gettext as _

from .forms import BookFilterForm, BookForm
from .models import Book, Category

logger = logging.getLogger(__name__)


class BookListView(ListView):
    """Список книг із пошуком, фільтрами за категорією/наявністю та пагінацією.

    Доступний усім відвідувачам без автентифікації — перегляд каталогу
    не обмежується.
    """

    model = Book
    paginate_by = 6
    context_object_name = "books"

    @cached_property
    def filter_form(self) -> BookFilterForm:
        """Форма з параметрами фільтрації з query string (створюється один раз на запит)."""
        return BookFilterForm(self.request.GET)

    def get_queryset(self) -> QuerySet[Book]:
        """Книги з урахуванням фільтрів. Порядок `title, pk` — детермінований, тож пагінація
        не «дублює» й не губить книги з однаковою назвою між сторінками."""
        queryset = Book.objects.select_related("category")
        return self.filter_form.filter(queryset).order_by("title", "pk")

    def get_context_data(self, **kwargs):
        """Додає категорії для фільтра, поточні значення фільтрів і query string для пагінації."""
        context = super().get_context_data(**kwargs)
        values = self.filter_form.cleaned_values()
        context["categories"] = Category.objects.annotate(book_count=Count("books"))
        context["current_query"] = values["q"]
        context["current_category"] = values["category"]
        context["current_stock"] = values["stock"]

        # querystring без 'page' — щоб пагінація зберігала активні фільтри
        params = self.request.GET.copy()
        params.pop("page", None)
        context["querystring"] = params.urlencode()
        return context


class BookDetailView(DetailView):
    """Детальна сторінка книги. Доступна всім без автентифікації."""

    model = Book
    context_object_name = "book"
    queryset = Book.objects.select_related("category")


class BookCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Додавання нової книги.

    Потребує логіну (LoginRequiredMixin) і права 'catalog.add_book'
    (PermissionRequiredMixin) — це право за замовчуванням видається
    групі "Бібліотекарі" (див. management-команду setup_groups).
    """

    model = Book
    form_class = BookForm
    permission_required = "catalog.add_book"

    def form_valid(self, form):
        """Зберігає книгу, проставляє автора запису (`created_by`), показує повідомлення й логує подію.

        Args:
            form: валідна `BookForm`.

        Returns:
            HTTP-редирект на сторінку створеної книги."""
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, _("Книгу «%(title)s» додано.") % {"title": self.object.title})
        logger.info(
            "Книгу #%s «%s» додав користувач %s",
            self.object.pk,
            self.object.title,
            self.request.user.get_username(),
        )
        return response


class BookUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Редагування існуючої книги. Потребує права 'catalog.change_book'."""

    model = Book
    form_class = BookForm
    permission_required = "catalog.change_book"

    def form_valid(self, form):
        """Зберігає зміни, показує повідомлення й логує, хто саме оновив книгу.

        Args:
            form: валідна `BookForm`.

        Returns:
            HTTP-редирект на сторінку книги."""
        response = super().form_valid(form)
        messages.success(self.request, _("Книгу «%(title)s» оновлено.") % {"title": self.object.title})
        logger.info(
            "Книгу #%s «%s» оновив користувач %s",
            self.object.pk,
            self.object.title,
            self.request.user.get_username(),
        )
        return response


class BookDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """Видалення книги з підтвердженням. Потребує права 'catalog.delete_book'."""

    model = Book
    success_url = reverse_lazy("catalog:book-list")
    permission_required = "catalog.delete_book"

    def form_valid(self, form):
        """Видаляє книгу після підтвердження, показує повідомлення й логує подію.

        Назва та pk запам'ятовуються до видалення, бо після нього об'єкт уже не має pk.

        Args:
            form: порожня форма підтвердження (DeleteView у Django 4+ видаляє у `form_valid`).

        Returns:
            HTTP-редирект на список книг."""
        title = self.object.title
        pk = self.object.pk
        response = super().form_valid(form)
        messages.success(self.request, _("Книгу «%(title)s» видалено.") % {"title": title})
        logger.info(
            "Книгу #%s «%s» видалив користувач %s",
            pk,
            title,
            self.request.user.get_username(),
        )
        return response


class CategoryListView(ListView):
    """Список категорій з кількістю книг у кожній (для навігації/фільтрів)."""

    model = Category
    context_object_name = "categories"

    def get_queryset(self) -> QuerySet[Category]:
        """Категорії з кількістю книг у кожній.

        Returns:
            QuerySet категорій, анотований полем `book_count`."""
        return Category.objects.annotate(book_count=Count("books"))
