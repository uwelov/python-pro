"""Форми застосунку catalog."""

from __future__ import annotations

from django import forms

from django.db.models import Q, QuerySet
from django.utils.translation import gettext_lazy as _

from .models import Book


class BookForm(forms.ModelForm):
    """Форма додавання/редагування книги з Bootstrap-класами для полів."""

    class Meta:
        model = Book
        fields = ["title", "author", "price", "description", "stock", "category"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "author": forms.TextInput(attrs={"class": "form-control"}),
            "price": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "description": forms.Textarea(
                attrs={"class": "form-control", "rows": 4}
            ),
            "stock": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "category": forms.Select(attrs={"class": "form-select"}),
        }


class BookFilterForm(forms.Form):
    """Валідація параметрів фільтрації каталогу (?q=, ?category=, ?stock=) з GET-запиту.

    Некоректні значення (напр. ?stock=banana) тихо ігноруються і не потрапляють ні у фільтр,
    ні в контекст шаблону. Логіка фільтрації живе тут, а не у view, тож її можна тестувати окремо.
    """

    q = forms.CharField(required=False, strip=True)
    category = forms.CharField(required=False, strip=True)
    stock = forms.ChoiceField(
        required=False,
        choices=[("in_stock", _("В наявності")), ("out_of_stock", _("Немає в наявності"))],
    )

    def cleaned_values(self) -> dict[str, str]:
        """Очищені значення всіх полів; для відсутніх або некоректних — порожній рядок."""
        self.is_valid()  # заповнює cleaned_data валідними полями; помилок не піднімає
        return {name: self.cleaned_data.get(name, "") for name in self.fields}

    def filter(self, queryset: QuerySet) -> QuerySet:
        """Застосовує очищені параметри до QuerySet книг."""
        values = self.cleaned_values()
        if values["q"]:
            queryset = queryset.filter(
                Q(title__icontains=values["q"]) | Q(author__icontains=values["q"])
            )
        if values["category"]:
            queryset = queryset.filter(category__slug=values["category"])
        if values["stock"] == "in_stock":
            queryset = queryset.filter(stock__gt=0)
        elif values["stock"] == "out_of_stock":
            queryset = queryset.filter(stock=0)
        return queryset
