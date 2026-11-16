"""Форми застосунку orders."""

from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _


class CheckoutForm(forms.Form):
    """Контактні дані для оформлення замовлення."""

    full_name = forms.CharField(
        label=_("Ім'я та прізвище"),
        max_length=255,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    email = forms.EmailField(
        label=_("Електронна пошта"),
        help_text=_("Сюди надійде підтвердження замовлення."),
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )
    phone = forms.CharField(
        label=_("Телефон"),
        max_length=32,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
