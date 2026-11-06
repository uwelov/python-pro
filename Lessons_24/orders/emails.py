"""Листи, що надсилаються клієнтам у зв'язку із замовленнями."""

from __future__ import annotations

import logging

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)


def send_order_created_email(order_id: int) -> bool:
    """Надсилає клієнту лист «Замовлення прийнято» (текст + HTML).

    Викликається через `transaction.on_commit`, тож працює вже після коміту.
    Помилку пошти тут тільки логуємо: замовлення вже створене, і його не можна
    «зламати» через недоступний SMTP-сервер.

    Returns:
        True, якщо лист надіслано.
    """
    from .models import Order  # імпорт тут, щоб уникнути циклічних залежностей

    try:
        order = Order.objects.prefetch_related("items").get(pk=order_id)
        context = {"order": order, "items": list(order.items.all())}

        message = EmailMultiAlternatives(
            subject=_("Замовлення №%(pk)s прийнято — Книжковий магазин") % {"pk": order.pk},
            body=render_to_string("orders/email/order_created.txt", context),
            to=[order.email],
        )
        message.attach_alternative(
            render_to_string("orders/email/order_created.html", context), "text/html"
        )
        message.send()
    except Exception:  # noqa: BLE001 — будь-яка помилка пошти не має ламати замовлення
        logger.exception("Не вдалося надіслати лист про замовлення #%s", order_id)
        return False

    logger.info("Лист про замовлення #%s надіслано на %s", order_id, order.email)
    return True
