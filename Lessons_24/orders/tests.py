"""Тести застосунку orders: кошик, створення замовлення, Stripe (з моком), вебхук, адмінка."""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
import time
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

import stripe
from django.contrib.auth import get_user_model
from django.core import mail
from django.db import connection
from django.test import TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.urls import reverse
from django.utils import translation

from catalog.models import Book, Category

from . import services
from .models import Order, OrderItem

User = get_user_model()

WEBHOOK_SECRET = "whsec_test_secret"
STRIPE_TEST_SETTINGS = dict(
    STRIPE_SECRET_KEY="sk_test_dummy",
    STRIPE_WEBHOOK_SECRET=WEBHOOK_SECRET,
    STRIPE_CURRENCY="uah",
)


def make_books():
    category = Category.objects.create(name="Тест", slug="test")
    book_a = Book.objects.create(title="Дюна", author="Герберт", price=Decimal("450.00"), stock=5, category=category)
    book_b = Book.objects.create(title="Кобзар", author="Шевченко", price=Decimal("150.50"), stock=2, category=category)
    return book_a, book_b


class BaseTestCase(TestCase):
    def setUp(self):
        self.book_a, self.book_b = make_books()
        self.user = User.objects.create_user("buyer", "buyer@example.com", "pw12345!")

    def add_to_cart(self, book, quantity=1, **extra):
        return self.client.post(
            reverse("orders:cart-add", args=[book.pk]), {"quantity": quantity, **extra}
        )

    def cart_in_session(self):
        return self.client.session.get("cart", {})


# ------------------------------------------------------------------ Кошик

class CartTests(BaseTestCase):
    def test_add_and_accumulate(self):
        self.add_to_cart(self.book_a, 2)
        self.add_to_cart(self.book_a, 1)
        self.assertEqual(self.cart_in_session(), {str(self.book_a.pk): 3})

    def test_quantity_is_clamped_to_stock(self):
        self.add_to_cart(self.book_b, 10)  # на складі 2
        self.assertEqual(self.cart_in_session(), {str(self.book_b.pk): 2})

    def test_override_replaces_quantity(self):
        self.add_to_cart(self.book_a, 3)
        self.add_to_cart(self.book_a, 1, override="1")
        self.assertEqual(self.cart_in_session(), {str(self.book_a.pk): 1})

    def test_override_to_zero_removes_item(self):
        self.add_to_cart(self.book_a, 3)
        self.add_to_cart(self.book_a, 0, override="1")
        self.assertEqual(self.cart_in_session(), {})

    def test_out_of_stock_book_is_not_added(self):
        self.book_b.stock = 0
        self.book_b.save()
        self.add_to_cart(self.book_b, 1)
        self.assertEqual(self.cart_in_session(), {})

    def test_remove(self):
        self.add_to_cart(self.book_a)
        self.add_to_cart(self.book_b)
        self.client.post(reverse("orders:cart-remove", args=[self.book_a.pk]))
        self.assertEqual(self.cart_in_session(), {str(self.book_b.pk): 1})

    def test_clear(self):
        self.add_to_cart(self.book_a)
        self.client.post(reverse("orders:cart-clear"))
        self.assertEqual(self.cart_in_session(), {})

    def test_cart_page_shows_total_and_counter(self):
        self.add_to_cart(self.book_a, 2)  # 900.00
        self.add_to_cart(self.book_b, 1)  # 150.50
        response = self.client.get(reverse("orders:cart-detail"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_price"], Decimal("1050.50"))
        self.assertEqual(len(response.context["cart"]), 3)

    def test_deleted_book_is_dropped_from_cart(self):
        self.add_to_cart(self.book_a)
        self.book_a.delete()
        response = self.client.get(reverse("orders:cart-detail"))
        self.assertEqual(response.context["items"], [])
        self.assertEqual(self.cart_in_session(), {})

    def test_cart_actions_require_post(self):
        self.assertEqual(self.client.get(reverse("orders:cart-add", args=[self.book_a.pk])).status_code, 405)

    def test_open_redirect_is_blocked(self):
        response = self.add_to_cart(self.book_a, next="https://evil.example.com/")
        self.assertRedirects(response, reverse("orders:cart-detail"))

    def test_anonymous_visit_does_not_create_session(self):
        self.client.get(reverse("catalog:book-list"))
        self.assertNotIn("sessionid", self.client.cookies)


# ------------------------------------------- Створення замовлення (atomic)

class CreateOrderServiceTests(BaseTestCase):
    def create(self, lines):
        return services.create_order(
            user=self.user, full_name="Іван Тест", email="ivan@example.com", phone="+380", lines=lines
        )

    def test_creates_order_items_and_reserves_stock(self):
        order = self.create([(self.book_a.pk, 2), (self.book_b.pk, 1)])

        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(order.get_total_cost(), Decimal("1050.50"))
        self.book_a.refresh_from_db(); self.book_b.refresh_from_db()
        self.assertEqual((self.book_a.stock, self.book_b.stock), (3, 1))

    def test_price_and_title_are_snapshotted(self):
        order = self.create([(self.book_a.pk, 1)])
        self.book_a.price = Decimal("999.00")
        self.book_a.title = "Нова назва"
        self.book_a.save()
        item = order.items.get()
        self.assertEqual((item.price, item.book_title), (Decimal("450.00"), "Дюна"))

    def test_order_survives_book_deletion(self):
        order = self.create([(self.book_a.pk, 1)])
        self.book_a.delete()
        item = order.items.get()
        self.assertIsNone(item.book)
        self.assertEqual(item.book_title, "Дюна")

    def test_insufficient_stock_rolls_back_everything(self):
        # Перша позиція валідна (і вже «списана»), друга — ні: має відкотитись усе.
        with self.assertRaises(services.InsufficientStockError):
            self.create([(self.book_a.pk, 1), (self.book_b.pk, 99)])

        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderItem.objects.count(), 0)
        self.book_a.refresh_from_db()
        self.assertEqual(self.book_a.stock, 5)

    def test_empty_order_is_rejected(self):
        with self.assertRaises(services.EmptyOrderError):
            self.create([])

    def test_email_is_sent_only_after_commit(self):
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            self.create([(self.book_a.pk, 1)])
        self.assertEqual(len(mail.outbox), 0)  # ще не закомічено
        self.assertEqual(len(callbacks), 1)

        for callback in callbacks:
            callback()
        self.assertEqual(len(mail.outbox), 1)

    def test_email_content(self):
        with translation.override("en"), self.captureOnCommitCallbacks(execute=True):
            order = self.create([(self.book_a.pk, 2)])
        message = mail.outbox[0]
        self.assertEqual(message.to, ["ivan@example.com"])
        self.assertIn(f"#{order.pk}", message.subject)  # en: "Order #N"
        self.assertIn("Дюна", message.body)
        self.assertIn("900.00", message.body)
        self.assertEqual(message.alternatives[0].mimetype, "text/html")

    def test_no_email_when_transaction_rolled_back(self):
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(services.InsufficientStockError):
                self.create([(self.book_b.pk, 99)])
        self.assertEqual(len(mail.outbox), 0)

    def test_email_failure_does_not_break_order(self):
        with mock.patch("django.core.mail.EmailMultiAlternatives.send", side_effect=OSError("smtp down")):
            with self.captureOnCommitCallbacks(execute=True):
                order = self.create([(self.book_a.pk, 1)])
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())

    def test_cancel_restores_stock_and_is_idempotent(self):
        order = self.create([(self.book_a.pk, 2)])
        self.assertTrue(services.cancel_order(order.pk))
        self.assertFalse(services.cancel_order(order.pk))
        self.book_a.refresh_from_db(); order.refresh_from_db()
        self.assertEqual(self.book_a.stock, 5)
        self.assertEqual(order.status, Order.Status.CANCELLED)

    def test_mark_paid_is_idempotent(self):
        order = self.create([(self.book_a.pk, 1)])
        self.assertTrue(services.mark_order_paid(order.pk, session_id="cs_1", payment_intent_id="pi_1"))
        self.assertFalse(services.mark_order_paid(order.pk))
        order.refresh_from_db()
        self.assertEqual((order.status, order.stripe_payment_intent_id), (Order.Status.PAID, "pi_1"))
        self.assertIsNotNone(order.paid_at)

    def test_paid_order_cannot_be_cancelled(self):
        order = self.create([(self.book_a.pk, 1)])
        services.mark_order_paid(order.pk)
        self.assertFalse(services.cancel_order(order.pk))

    def test_payment_for_cancelled_order_is_not_resurrected(self):
        order = self.create([(self.book_a.pk, 1)])
        services.cancel_order(order.pk)
        self.assertFalse(services.mark_order_paid(order.pk))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)


class ConcurrentOrderTests(TransactionTestCase):
    """select_for_update: два одночасні замовлення на останній примірник — успішне лише одне."""

    @skipUnlessDBFeature("has_select_for_update")
    def test_no_overselling(self):
        category = Category.objects.create(name="C", slug="c")
        book = Book.objects.create(title="Остання", author="A", price=10, stock=1, category=category)
        user = User.objects.create_user("u", "u@example.com", "x")
        results, barrier = [], threading.Barrier(2)

        def worker():
            try:
                barrier.wait()
                services.create_order(user=user, full_name="N", email="n@example.com", lines=[(book.pk, 1)])
                results.append("ok")
            except services.InsufficientStockError:
                results.append("no stock")
            finally:
                connection.close()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        [t.start() for t in threads]
        [t.join() for t in threads]

        self.assertEqual(sorted(results), ["no stock", "ok"])
        book.refresh_from_db()
        self.assertEqual(book.stock, 0)


# --------------------------------------------- Оформлення та оплата (Stripe)

@override_settings(**STRIPE_TEST_SETTINGS)
class CheckoutFlowTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="buyer", password="pw12345!")
        self.checkout_data = {"full_name": "Іван Тест", "email": "ivan@example.com", "phone": ""}

    def fake_session(self, **overrides):
        data = dict(id="cs_test_123", url="https://checkout.stripe.com/pay/cs_test_123",
                    payment_status="unpaid", payment_intent=None)
        data.update(overrides)
        return SimpleNamespace(**data)

    def test_checkout_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("orders:checkout"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_empty_cart_redirects_to_cart(self):
        response = self.client.get(reverse("orders:checkout"))
        self.assertRedirects(response, reverse("orders:cart-detail"))

    def test_successful_checkout(self):
        self.add_to_cart(self.book_a, 2)
        self.add_to_cart(self.book_b, 1)

        with mock.patch("orders.payments.stripe.checkout.Session.create", return_value=self.fake_session()) as create:
            response = self.client.post(reverse("orders:checkout"), self.checkout_data)

        # редірект 303 на Stripe
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response["Location"], "https://checkout.stripe.com/pay/cs_test_123")

        order = Order.objects.get()
        self.assertEqual((order.user, order.status, order.stripe_session_id), (self.user, "pending", "cs_test_123"))
        self.assertEqual(self.cart_in_session(), {})  # кошик очищено
        self.assertEqual(len(mail.outbox), 1)  # лист про створення
        self.assertEqual(mail.outbox[0].to, ["ivan@example.com"])

        # що саме відправлено у Stripe
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["mode"], "payment")
        self.assertEqual(kwargs["client_reference_id"], str(order.pk))
        self.assertEqual(kwargs["metadata"], {"order_id": str(order.pk)})
        amounts = {li["price_data"]["product_data"]["name"]: (li["price_data"]["unit_amount"], li["quantity"])
                   for li in kwargs["line_items"]}
        self.assertEqual(amounts, {"Дюна": (45000, 2), "Кобзар": (15050, 1)})
        self.assertEqual(kwargs["line_items"][0]["price_data"]["currency"], "uah")
        self.assertIn("{CHECKOUT_SESSION_ID}", kwargs["success_url"])

    def test_stripe_failure_cancels_order_and_keeps_cart(self):
        self.add_to_cart(self.book_a, 2)
        with mock.patch("orders.payments.stripe.checkout.Session.create", side_effect=stripe.APIConnectionError("boom")):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(reverse("orders:checkout"), self.checkout_data)

        self.assertRedirects(response, reverse("orders:checkout"))
        self.assertEqual(len(mail.outbox), 0)  # про невдале оформлення листа немає
        order = Order.objects.get()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.book_a.refresh_from_db()
        self.assertEqual(self.book_a.stock, 5)  # склад відновлено
        self.assertEqual(self.cart_in_session(), {str(self.book_a.pk): 2})  # кошик цілий

    @override_settings(STRIPE_SECRET_KEY="")
    def test_missing_stripe_key_is_handled(self):
        self.add_to_cart(self.book_a)
        response = self.client.post(reverse("orders:checkout"), self.checkout_data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.get().status, Order.Status.CANCELLED)

    def test_stock_shortage_at_checkout(self):
        self.add_to_cart(self.book_b, 2)
        Book.objects.filter(pk=self.book_b.pk).update(stock=1)  # хтось купив раніше
        response = self.client.post(reverse("orders:checkout"), self.checkout_data)
        self.assertRedirects(response, reverse("orders:cart-detail"))
        self.assertEqual(Order.objects.count(), 0)

    def test_invalid_form_creates_nothing(self):
        self.add_to_cart(self.book_a)
        response = self.client.post(reverse("orders:checkout"), {"full_name": "", "email": "not-an-email"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), 0)

    def test_success_page_marks_order_paid(self):
        order = services.create_order(user=self.user, full_name="N", email="n@example.com",
                                      lines=[(self.book_a.pk, 1)])
        Order.objects.filter(pk=order.pk).update(stripe_session_id="cs_test_123")
        paid = self.fake_session(payment_status="paid", payment_intent="pi_999")

        with mock.patch("orders.payments.stripe.checkout.Session.retrieve", return_value=paid):
            response = self.client.get(
                reverse("orders:order-success", args=[order.pk]) + "?session_id=cs_test_123"
            )

        self.assertRedirects(response, order.get_absolute_url())
        order.refresh_from_db()
        self.assertEqual((order.status, order.stripe_payment_intent_id), ("paid", "pi_999"))

    def test_success_page_with_wrong_session_id_does_not_pay(self):
        order = services.create_order(user=self.user, full_name="N", email="n@example.com",
                                      lines=[(self.book_a.pk, 1)])
        Order.objects.filter(pk=order.pk).update(stripe_session_id="cs_real")
        with mock.patch("orders.payments.stripe.checkout.Session.retrieve") as retrieve:
            self.client.get(reverse("orders:order-success", args=[order.pk]) + "?session_id=cs_forged")
        retrieve.assert_not_called()
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_retry_payment_creates_new_session(self):
        order = services.create_order(user=self.user, full_name="N", email="n@example.com",
                                      lines=[(self.book_a.pk, 1)])
        with mock.patch("orders.payments.stripe.checkout.Session.create",
                        return_value=self.fake_session(id="cs_new", url="https://stripe.test/new")):
            response = self.client.post(reverse("orders:order-pay", args=[order.pk]))
        self.assertEqual(response["Location"], "https://stripe.test/new")
        order.refresh_from_db()
        self.assertEqual(order.stripe_session_id, "cs_new")

    def test_user_cancels_pending_order(self):
        order = services.create_order(user=self.user, full_name="N", email="n@example.com",
                                      lines=[(self.book_a.pk, 3)])
        self.client.post(reverse("orders:order-cancel", args=[order.pk]))
        order.refresh_from_db(); self.book_a.refresh_from_db()
        self.assertEqual((order.status, self.book_a.stock), ("cancelled", 5))


class OrderAccessTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.order = services.create_order(user=self.user, full_name="N", email="n@example.com",
                                           lines=[(self.book_a.pk, 1)])
        self.other = User.objects.create_user("other", "o@example.com", "pw12345!")

    def test_owner_sees_order(self):
        self.client.login(username="buyer", password="pw12345!")
        self.assertEqual(self.client.get(self.order.get_absolute_url()).status_code, 200)
        self.assertContains(self.client.get(reverse("orders:order-list")), f"{self.order.pk}")

    def test_other_user_gets_404(self):
        self.client.login(username="other", password="pw12345!")
        self.assertEqual(self.client.get(self.order.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.post(reverse("orders:order-cancel", args=[self.order.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse("orders:order-list")), "Дюна")

    def test_anonymous_is_redirected_to_login(self):
        self.assertEqual(self.client.get(self.order.get_absolute_url()).status_code, 302)


# ------------------------------------------------------------------ Вебхук

def sign(payload: str, secret: str = WEBHOOK_SECRET) -> str:
    """Генерує справжній заголовок Stripe-Signature (t=...,v1=HMAC-SHA256)."""
    timestamp = int(time.time())
    digest = hmac.new(secret.encode(), f"{timestamp}.{payload}".encode(), hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


@override_settings(**STRIPE_TEST_SETTINGS)
class WebhookTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.order = services.create_order(user=self.user, full_name="N", email="n@example.com",
                                           lines=[(self.book_a.pk, 2)])
        self.order_id = self.order.pk  # pk зникає після .delete()

    def post_event(self, event_type, *, signature=None, **object_fields):
        obj = {"id": "cs_test_1", "object": "checkout.session", "payment_status": "paid",
               "payment_intent": "pi_1", "client_reference_id": str(self.order_id),
               "metadata": {"order_id": str(self.order_id)}, **object_fields}
        payload = json.dumps({"id": "evt_1", "object": "event", "type": event_type, "data": {"object": obj}})
        return self.client.post(
            reverse("orders:stripe-webhook"), payload, content_type="application/json",
            HTTP_STRIPE_SIGNATURE=signature or sign(payload),
        )

    def test_completed_marks_order_paid(self):
        response = self.post_event("checkout.session.completed")
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual((self.order.status, self.order.stripe_payment_intent_id), ("paid", "pi_1"))

    def test_replayed_event_is_harmless(self):
        self.post_event("checkout.session.completed")
        self.assertEqual(self.post_event("checkout.session.completed").status_code, 200)
        self.assertEqual(Order.objects.get().status, "paid")

    def test_unpaid_completed_event_does_not_pay(self):
        self.post_event("checkout.session.completed", payment_status="unpaid")
        self.assertEqual(Order.objects.get().status, "pending")

    def test_expired_cancels_order_and_restores_stock(self):
        self.post_event("checkout.session.expired", payment_status="unpaid")
        self.book_a.refresh_from_db()
        self.assertEqual(Order.objects.get().status, "cancelled")
        self.assertEqual(self.book_a.stock, 5)

    def test_invalid_signature_is_rejected(self):
        response = self.post_event("checkout.session.completed", signature="t=1,v1=deadbeef")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.get().status, "pending")

    def test_signature_with_wrong_secret_is_rejected(self):
        payload = "{}"
        response = self.client.post(reverse("orders:stripe-webhook"), payload, content_type="application/json",
                                    HTTP_STRIPE_SIGNATURE=sign(payload, secret="whsec_other"))
        self.assertEqual(response.status_code, 400)

    def test_missing_signature_is_rejected(self):
        response = self.client.post(reverse("orders:stripe-webhook"), "{}", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_unknown_order_returns_200(self):
        self.order.delete()
        self.assertEqual(self.post_event("checkout.session.completed").status_code, 200)

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(reverse("orders:stripe-webhook")).status_code, 405)

    def test_csrf_not_required(self):
        from django.test import Client
        strict = Client(enforce_csrf_checks=True)
        self.assertEqual(strict.post(reverse("orders:stripe-webhook"), "{}", content_type="application/json").status_code, 400)


# ------------------------------------------------------------------ Адмінка

class AdminTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser("root", "root@example.com", "pw12345!")
        self.client.login(username="root", password="pw12345!")
        self.order = services.create_order(user=self.user, full_name="Іван", email="i@example.com",
                                           lines=[(self.book_a.pk, 2), (self.book_b.pk, 1)])

    def test_changelist_shows_total(self):
        response = self.client.get(reverse("admin:orders_order_changelist"), headers={"accept-language": "en"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1050.50")

    def test_change_page_has_orderitem_inline(self):
        response = self.client.get(reverse("admin:orders_order_change", args=[self.order.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "items-TOTAL_FORMS")
        self.assertContains(response, "Дюна")
        self.assertContains(response, "Кобзар")

    def test_search_and_filter(self):
        url = reverse("admin:orders_order_changelist")
        # пошук за ім'ям кирилицею (перевіряє і unicode-LIKE на SQLite) та за email
        self.assertContains(self.client.get(url, {"q": "іван"}), "i@example.com")
        self.assertContains(self.client.get(url, {"q": "i@example.com"}), "i@example.com")
        self.assertNotContains(self.client.get(url, {"q": "nobody"}), "i@example.com")
        # пошук за номером замовлення (числове поле id)
        self.assertContains(self.client.get(url, {"q": str(self.order.pk)}), "i@example.com")
        # фільтр за статусом
        self.assertNotContains(self.client.get(url, {"status__exact": "paid"}), "i@example.com")
        self.assertContains(self.client.get(url, {"status__exact": "pending"}), "i@example.com")
