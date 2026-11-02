"""Форми реєстрації/автентифікації застосунку accounts."""

from __future__ import annotations

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User

_BOOTSTRAP_TEXT = {"class": "form-control"}


class RegisterForm(UserCreationForm):
    """Форма реєстрації: стандартні username/password1/password2 + email/телефон."""

    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs=_BOOTSTRAP_TEXT))

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "phone_number")
        widgets = {
            "username": forms.TextInput(attrs=_BOOTSTRAP_TEXT),
            "phone_number": forms.TextInput(attrs=_BOOTSTRAP_TEXT),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget.attrs.update(_BOOTSTRAP_TEXT)
        self.fields["password2"].widget.attrs.update(_BOOTSTRAP_TEXT)


class LoginForm(AuthenticationForm):
    """AuthenticationForm із Bootstrap-класами на полях."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(_BOOTSTRAP_TEXT)
        self.fields["password"].widget.attrs.update(_BOOTSTRAP_TEXT)
