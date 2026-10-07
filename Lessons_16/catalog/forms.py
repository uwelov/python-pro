"""Форми застосунку catalog."""

from __future__ import annotations

from django import forms

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
