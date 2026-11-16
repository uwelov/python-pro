"""Context processors застосунку orders."""

from __future__ import annotations

from django.http import HttpRequest

from .cart import Cart


def cart(request: HttpRequest) -> dict[str, Cart]:
    """Робить `cart` доступним у всіх шаблонах (лічильник у navbar)."""
    return {"cart": Cart(request)}
