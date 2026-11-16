"""Бізнес-логіка замовлень: створення, скасування, позначення оплаченим.

Усі функції, що змінюють кілька таблиць (Order, OrderItem, Book.stock), працюють
в `transaction.atomic`: або виконується все, або нічого. Рядки Book блокуються
через `select_for_update`, щоб два одночасні замовлення не «продали» один і той
самий останній примірник.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import timedelta
from functools import partial

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from catalog.models import Book

from . import payments
from .emails import send_order_created_email
from .models import Order, OrderItem

logger = logging.getLogger(__name__)


class OrderError(Exception):
    """Базова помилка оформлення замовлення."""


class EmptyOrderError(OrderError):
    """У замовленні немає жодної позиції."""


class InsufficientStockError(OrderError):
    """На складі менше книг, ніж замовлено (або книгу видалено)."""

    def __init__(self, title: str, requested: int, available: int) -> None:
        self.title = title
        self.requested = requested
        self.available = available
        super().__init__(
            _("«%(title)s»: замовлено %(requested)d, на складі %(available)d.")
            % {"title": title, "requested": requested, "available": available}
        )


def _lock_books(book_ids: Iterable[int]) -> dict[int, Book]:
    """Блокує рядки книг до кінця транзакції. Порядок за pk — щоб уникнути deadlock."""
    books = Book.objects.select_for_update().filter(pk__in=list(book_ids)).order_by("pk")
    return {book.pk: book for book in books}


@transaction.atomic
def create_order(
    *,
    user,
    full_name: str,
    email: str,
    phone: str = "",
    lines: Iterable[tuple[int, int]],
    notify: bool = True,
) -> Order:
    """Створює замовлення, фіксує ціни та резервує книги на складі.

    Args:
        user: автор замовлення.
        full_name, email, phone: контактні дані.
        lines: послідовність (id_книги, кількість).
        notify: чи ставити лист клієнту в on_commit. Потік оформлення з оплатою
            передає False і шле лист сам, коли платіжну сесію вже створено.

    Raises:
        EmptyOrderError: немає позицій.
        InsufficientStockError: якоїсь книги не вистачає. Транзакція відкочується
            повністю — не лишається ні замовлення, ні «зайвих» списань зі складу.

    Лист клієнту ставиться в `transaction.on_commit`, тобто надсилається лише
    після успішного коміту (якщо транзакцію відкотило — листа не буде).
    """
    lines = list(lines)
    if not lines:
        raise EmptyOrderError(_("Кошик порожній."))

    books = _lock_books(book_id for book_id, _ in lines)

    order = Order.objects.create(
        user=user, full_name=full_name, email=email, phone=phone
    )

    items: list[OrderItem] = []
    for book_id, quantity in lines:
        book = books.get(book_id)
        if book is None:
            raise InsufficientStockError(_("(книгу видалено)"), quantity, 0)
        if book.stock < quantity:
            raise InsufficientStockError(book.title, quantity, book.stock)

        book.stock -= quantity
        book.save(update_fields=["stock"])
        items.append(
            OrderItem(
                order=order,
                book=book,
                book_title=book.title,
                price=book.price,  # snapshot ціни
                quantity=quantity,
            )
        )
    OrderItem.objects.bulk_create(items)

    logger.info("Створено замовлення #%s (%s позицій)", order.pk, len(items))
    if notify:
        transaction.on_commit(partial(send_order_created_email, order.pk))
    return order


@transaction.atomic
def cancel_order(order_id: int) -> bool:
    """Скасовує неоплачене замовлення й повертає книги на склад.

    Returns:
        True, якщо скасовано; False, якщо замовлення вже не в стані "очікує оплати"
        (повторний виклик нічого не псує — функція ідемпотентна).
    """
    order = Order.objects.select_for_update().get(pk=order_id)
    if order.status != Order.Status.PENDING:
        return False

    items = list(order.items.exclude(book__isnull=True))
    books = _lock_books(item.book_id for item in items)
    for item in items:
        book = books[item.book_id]
        book.stock += item.quantity
        book.save(update_fields=["stock"])

    order.status = Order.Status.CANCELLED
    order.save(update_fields=["status", "updated_at"])
    logger.info("Замовлення #%s скасовано, склад відновлено", order.pk)
    return True


@transaction.atomic
def cancel_stale_orders(*, older_than: timedelta) -> int:
    """Скасовує неоплачені замовлення, старші за `older_than`, і повертає книги на склад.

    Страхує від ситуації, коли вебхук `checkout.session.expired` не дійшов (або не налаштований):
    без цього резерв на складі висів би вічно. Кожне замовлення скасовується окремо
    (`cancel_order` ідемпотентна), тож збій одного не блокує решту.

    Returns:
        Кількість скасованих замовлень.
    """
    cutoff = timezone.now() - older_than
    stale_ids = list(
        Order.objects.filter(status=Order.Status.PENDING, created_at__lt=cutoff).values_list("pk", flat=True)
    )
    return sum(1 for order_id in stale_ids if cancel_order(order_id))


@transaction.atomic
def mark_order_paid(
    order_id: int,
    *,
    session_id: str = "",
    payment_intent_id: str = "",
    amount_total: int | None = None,
    currency: str | None = None,
) -> bool:
    """Позначає замовлення оплаченим. Ідемпотентна: можна викликати з вебхука і зі сторінки успіху.

    Args:
        order_id: id замовлення.
        session_id, payment_intent_id: ідентифікатори Stripe для запису в замовлення.
        amount_total: сума, яку фактично сплатили (в мінорних одиницях, з Stripe-сесії).
        currency: валюта платежу. Якщо `amount_total`/`currency` передано — вони мають збігатися
            із сумою та валютою замовлення (defense in depth: не довіряємо подіям «наосліп»).

    Returns:
        True — статус змінено щойно; False — вже було оплачено, скасовано або сума/валюта не збіглись.
    """
    order = Order.objects.select_for_update().get(pk=order_id)

    if order.status == Order.Status.PAID:
        return False
    if order.status == Order.Status.CANCELLED:
        # Гроші прийшли за замовлення, яке вже скасоване (склад відпущено).
        # Автоматично не «воскрешаємо» — потрібне ручне рішення (повернення коштів).
        logger.error(
            "Оплата отримана за скасоване замовлення #%s — потрібне ручне втручання/refund",
            order.pk,
        )
        return False

    expected_currency = settings.STRIPE_CURRENCY
    expected_amount = payments.to_minor_units(order.get_total_cost(), expected_currency)
    if (amount_total is not None and amount_total != expected_amount) or (
        currency is not None and currency.lower() != expected_currency
    ):
        logger.error(
            "Оплата за замовлення #%s не збігається із замовленням: отримано %s %s, очікувалось %s %s",
            order.pk, amount_total, currency, expected_amount, expected_currency,
        )
        return False

    order.status = Order.Status.PAID
    order.paid_at = timezone.now()
    if session_id:
        order.stripe_session_id = session_id
    if payment_intent_id:
        order.stripe_payment_intent_id = payment_intent_id
    order.save()
    logger.info("Замовлення #%s оплачено", order.pk)
    return True
