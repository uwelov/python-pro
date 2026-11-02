"""Форми застосунку orders."""

from __future__ import annotations

from django import forms


class CheckoutForm(forms.Form):
    """Контактні дані для оформлення замовлення."""

    full_name = forms.CharField(
        label="Ім'я та прізвище",
        max_length=255,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    email = forms.EmailField(
        label="Email",
        help_text="Сюди надійде підтвердження замовлення.",
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )
    phone = forms.CharField(
        label="Телефон",
        max_length=32,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
