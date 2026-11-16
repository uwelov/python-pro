"""Кошик товарів, що зберігається в сесії користувача (request.session).

У сесії лежить лише словник {id_книги: кількість} — без цін і назв, тому ціни
в кошику завжди актуальні (беруться з БД), а сама сесія залишається маленькою.
Ціна «фіксується» в момент оформлення замовлення (див. OrderItem.price).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterator, TypedDict

from django.conf import settings
from django.http import HttpRequest

from catalog.models import Book


class CartItem(TypedDict):
    """Один рядок кошика у вигляді, зручному для шаблону."""

    book: Book
    quantity: int
    price: Decimal
    total_price: Decimal
    over_stock: bool  # у кошику більше, ніж зараз є на складі


class Cart:
    def __init__(self, request: HttpRequest) -> None:
        self.session = request.session
        # .get(), а не setdefault(): так сесія не створюється для кожного
        # відвідувача, який ще нічого не додав у кошик.
        self.cart: dict[str, int] = dict(self.session.get(settings.CART_SESSION_ID) or {})

    def save(self) -> None:
        self.session[settings.CART_SESSION_ID] = self.cart
        self.session.modified = True

    def add(self, book: Book, quantity: int = 1, override_quantity: bool = False) -> int:
        """Додає книгу в кошик і повертає підсумкову кількість цієї книги в кошику.

        Args:
            book: книга.
            quantity: скільки додати (або яка кількість має бути, якщо override_quantity).
            override_quantity: True — замінити кількість, False — збільшити наявну.

        Кількість обмежується залишком на складі. Якщо вийшло 0 (нема в наявності
        або кількість <= 0) — позиція видаляється з кошика.
        """
        key = str(book.pk)
        current = self.cart.get(key, 0)
        wanted = quantity if override_quantity else current + quantity
        final = max(0, min(wanted, book.stock))

        if final == 0:
            self.cart.pop(key, None)
        else:
            self.cart[key] = final
        self.save()
        return final

    def remove(self, book: Book) -> None:
        """Видаляє книгу з кошика повністю (незалежно від кількості)."""
        if self.cart.pop(str(book.pk), None) is not None:
            self.save()

    def clear(self) -> None:
        """Повністю очищає кошик."""
        self.cart = {}
        self.session.pop(settings.CART_SESSION_ID, None)
        self.session.modified = True

    def lines(self) -> list[tuple[int, int]]:
        """Список (id_книги, кількість) — вхідні дані для створення замовлення."""
        return [(int(book_id), qty) for book_id, qty in self.cart.items()]

    def __iter__(self) -> Iterator[CartItem]:
        ids = [int(book_id) for book_id in self.cart]
        books = {b.pk: b for b in Book.objects.select_related("category").filter(pk__in=ids)}

        # Книги, видалені з каталогу, тихо прибираємо з кошика.
        missing = [str(i) for i in ids if i not in books]
        if missing:
            for key in missing:
                self.cart.pop(key, None)
            self.save()

        for book_id in ids:
            book = books.get(book_id)
            if book is None:
                continue
            quantity = self.cart[str(book_id)]
            yield CartItem(
                book=book,
                quantity=quantity,
                price=book.price,
                total_price=book.price * quantity,
                over_stock=quantity > book.stock,
            )

    def __len__(self) -> int:
        """Загальна кількість одиниць товару (без звернення до БД)."""
        return sum(self.cart.values())

    def get_total_price(self) -> Decimal:
        return sum((item["total_price"] for item in self), Decimal("0"))
