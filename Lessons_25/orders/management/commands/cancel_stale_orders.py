"""Скасовує неоплачені замовлення, що «зависли», і повертає книги на склад."""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand

from orders import services


class Command(BaseCommand):
    help = (
        "Скасовує замовлення зі статусом «очікує оплати», старші за заданий час, "
        "і знімає резерв книг. Страхує від втраченого вебхука checkout.session.expired."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--minutes",
            type=int,
            default=None,
            help="Вік замовлення в хвилинах. За замовчуванням: час життя Stripe-сесії + 10 хв запасу.",
        )

    def handle(self, *args, **options):
        minutes = options["minutes"]
        if minutes is None:
            minutes = settings.STRIPE_SESSION_TTL // 60 + 10
        cancelled = services.cancel_stale_orders(older_than=timedelta(minutes=minutes))
        self.stdout.write(
            self.style.SUCCESS(f"Скасовано прострочених замовлень (старших за {minutes} хв): {cancelled}")
        )
