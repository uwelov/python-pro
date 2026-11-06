"""Views кошика, оформлення замовлення, оплати Stripe та вебхука."""

from __future__ import annotations

import logging

import stripe
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ImproperlyConfigured
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, FormView, ListView, TemplateView
from django.utils.translation import gettext as _, ngettext

from catalog.models import Book

from . import payments, services
from .cart import Cart
from .emails import send_order_created_email
from .forms import CheckoutForm
from .models import Order

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------- Кошик

def _safe_next(request: HttpRequest, default: str) -> str:
    """Повертає ?next=/POST next, лише якщо він веде на наш сайт (захист від open redirect)."""
    target = request.POST.get("next") or request.GET.get("next") or ""
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return default


class CartDetailView(TemplateView):
    template_name = "orders/cart_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart = Cart(self.request)
        context["items"] = list(cart)
        context["total_price"] = sum((i["total_price"] for i in context["items"]), 0)
        return context


@require_POST
def cart_add(request: HttpRequest, book_id: int) -> HttpResponse:
    book = get_object_or_404(Book, pk=book_id)
    cart = Cart(request)

    try:
        quantity = int(request.POST.get("quantity", 1))
    except ValueError:
        quantity = 1
    override = request.POST.get("override") == "1"

    if book.stock == 0:
        messages.error(request, _("«%(title)s» немає в наявності.") % {"title": book.title})
    else:
        current = cart.cart.get(str(book.pk), 0)
        wanted = quantity if override else current + quantity
        final = cart.add(book, quantity=quantity, override_quantity=override)
        if final == 0:
            messages.info(request, _("«%(title)s» прибрано з кошика.") % {"title": book.title})
        elif wanted > book.stock:
            messages.warning(
                request,
                _("На складі лише %(stock)d шт. «%(title)s» — кількість обмежено.")
                % {"stock": book.stock, "title": book.title},
            )
        else:
            messages.success(
                request,
                ngettext(
                    "«%(title)s»: у кошику %(count)d примірник",
                    "«%(title)s»: у кошику %(count)d примірників",
                    final,
                )
                % {"title": book.title, "count": final},
            )

    return redirect(_safe_next(request, reverse("orders:cart-detail")))


@require_POST
def cart_remove(request: HttpRequest, book_id: int) -> HttpResponse:
    book = get_object_or_404(Book, pk=book_id)
    Cart(request).remove(book)
    messages.info(request, _("«%(title)s» прибрано з кошика.") % {"title": book.title})
    return redirect("orders:cart-detail")


@require_POST
def cart_clear(request: HttpRequest) -> HttpResponse:
    Cart(request).clear()
    messages.info(request, _("Кошик очищено."))
    return redirect("orders:cart-detail")


# ------------------------------------------------------------- Замовлення

def _redirect_to_stripe(request: HttpRequest, order: Order) -> HttpResponse:
    """Створює Checkout Session і перенаправляє клієнта на сторінку оплати Stripe."""
    success_url = request.build_absolute_uri(
        reverse("orders:order-success", kwargs={"pk": order.pk})
    ) + "?session_id={CHECKOUT_SESSION_ID}"
    cancel_url = request.build_absolute_uri(order.get_absolute_url())

    session = payments.create_checkout_session(
        order, success_url=success_url, cancel_url=cancel_url
    )
    Order.objects.filter(pk=order.pk).update(stripe_session_id=session.id)

    response = HttpResponse(status=303)  # 303 See Other — стандарт для редіректу після POST
    response["Location"] = session.url
    return response


class CheckoutView(LoginRequiredMixin, FormView):
    """Оформлення замовлення: контактні дані -> Order (atomic) -> оплата в Stripe."""

    template_name = "orders/checkout.html"
    form_class = CheckoutForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and len(Cart(request)) == 0:
            messages.info(request, _("Кошик порожній — додайте книги перед оформленням."))
            return redirect("orders:cart-detail")
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        user = self.request.user
        return {"full_name": user.get_full_name() or user.get_username(), "email": user.email}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart = Cart(self.request)
        context["items"] = list(cart)
        context["total_price"] = sum((i["total_price"] for i in context["items"]), 0)
        return context

    def form_valid(self, form):
        cart = Cart(self.request)
        try:
            order = services.create_order(
                user=self.request.user,
                lines=cart.lines(),
                notify=False,  # лист — після успішного створення платіжної сесії (нижче)
                **form.cleaned_data,
            )
        except services.InsufficientStockError as exc:
            messages.error(
                self.request,
                _("Не вдалося оформити замовлення. %(reason)s") % {"reason": exc},
            )
            return redirect("orders:cart-detail")
        except services.OrderError as exc:
            messages.error(self.request, str(exc))
            return redirect("orders:cart-detail")

        try:
            response = _redirect_to_stripe(self.request, order)
        except (stripe.StripeError, ImproperlyConfigured):
            logger.exception("Не вдалося створити Stripe Checkout Session для #%s", order.pk)
            services.cancel_order(order.pk)  # повертаємо книги на склад
            messages.error(
                self.request,
                _("Платіжна система тимчасово недоступна. Замовлення не створено, спробуйте ще раз."),
            )
            return redirect("orders:checkout")

        cart.clear()
        # Лист «замовлення прийнято» — лише тепер, коли оплата реально ініційована.
        send_order_created_email(order.pk)
        return response


class OrderOwnerMixin(LoginRequiredMixin):
    """Користувач бачить лише власні замовлення (персонал — усі)."""

    def get_queryset(self):
        queryset = Order.objects.prefetch_related("items")
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(user=self.request.user)


class OrderListView(OrderOwnerMixin, ListView):
    context_object_name = "orders"
    paginate_by = 10
    template_name = "orders/order_list.html"

    def get_queryset(self):
        # У списку «Мої замовлення» — завжди лише свої, навіть для персоналу.
        return Order.objects.prefetch_related("items").filter(user=self.request.user)


class OrderDetailView(OrderOwnerMixin, DetailView):
    context_object_name = "order"
    template_name = "orders/order_detail.html"


def _get_own_order(request: HttpRequest, pk: int) -> Order:
    if not request.user.is_authenticated:
        raise Http404
    queryset = Order.objects.all() if request.user.is_staff else Order.objects.filter(user=request.user)
    return get_object_or_404(queryset, pk=pk)


@require_POST
def order_pay(request: HttpRequest, pk: int) -> HttpResponse:
    """Повторна спроба оплати (нова Checkout Session) для неоплаченого замовлення."""
    order = _get_own_order(request, pk)
    if not order.is_pending:
        messages.info(request, _("Це замовлення не очікує оплати."))
        return redirect(order)
    try:
        return _redirect_to_stripe(request, order)
    except (stripe.StripeError, ImproperlyConfigured):
        logger.exception("Не вдалося створити Stripe Checkout Session для #%s", order.pk)
        messages.error(request, _("Платіжна система тимчасово недоступна. Спробуйте пізніше."))
        return redirect(order)


@require_POST
def order_cancel(request: HttpRequest, pk: int) -> HttpResponse:
    order = _get_own_order(request, pk)
    if services.cancel_order(order.pk):
        messages.info(
            request,
            _("Замовлення №%(pk)s скасовано, книги повернуто на склад.") % {"pk": order.pk},
        )
    else:
        messages.warning(request, _("Це замовлення вже не можна скасувати."))
    return redirect(order)


def order_success(request: HttpRequest, pk: int) -> HttpResponse:
    """Сторінка, на яку Stripe повертає клієнта після оплати.

    Статус оплати перевіряємо в самому Stripe (а не довіряємо query-параметру),
    тож це працює і без вебхука; вебхук — друга, незалежна лінія підтвердження.
    """
    order = _get_own_order(request, pk)
    session_id = request.GET.get("session_id", "")

    if order.is_paid:
        messages.success(request, _("Замовлення №%(pk)s оплачено. Дякуємо!") % {"pk": order.pk})
    elif session_id and session_id == order.stripe_session_id:
        try:
            session = payments.retrieve_session(session_id)
        except (stripe.StripeError, ImproperlyConfigured):
            logger.exception("Не вдалося перевірити сесію %s", session_id)
            messages.warning(request, _("Платіж обробляється. Статус оновиться за хвилину."))
        else:
            if session.payment_status == "paid":
                services.mark_order_paid(
                    order.pk,
                    session_id=session.id,
                    payment_intent_id=str(session.payment_intent or ""),
                )
                messages.success(request, _("Замовлення №%(pk)s оплачено. Дякуємо!") % {"pk": order.pk})
            else:
                messages.warning(request, _("Оплату ще не підтверджено."))
    else:
        messages.warning(request, _("Не вдалося підтвердити оплату цього замовлення."))

    return redirect(order)


# ----------------------------------------------------------------- Вебхук

@csrf_exempt
@require_POST
def stripe_webhook(request: HttpRequest) -> HttpResponse:
    """Приймає події Stripe. CSRF вимкнено свідомо: автентифікація — за підписом Stripe."""
    try:
        event = payments.construct_webhook_event(
            request.body, request.META.get("HTTP_STRIPE_SIGNATURE", "")
        )
    except ValueError:
        return HttpResponse(status=400)
    except stripe.SignatureVerificationError:
        logger.warning("Вебхук Stripe з недійсним підписом")
        return HttpResponse(status=400)

    # У новому SDK Stripe події — не dict; to_dict() дає звичайні словники.
    event = event.to_dict()
    event_type = event["type"]
    session = event["data"]["object"]
    order_id = (session.get("metadata") or {}).get("order_id") or session.get("client_reference_id")

    if event_type in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        if order_id and session.get("payment_status") == "paid":
            _safe_order_call(
                services.mark_order_paid,
                int(order_id),
                session_id=session.get("id") or "",
                payment_intent_id=str(session.get("payment_intent") or ""),
            )
    elif event_type == "checkout.session.expired":
        if order_id:
            _safe_order_call(services.cancel_order, int(order_id))

    return HttpResponse(status=200)


def _safe_order_call(func, order_id: int, **kwargs) -> None:
    """Вебхук для неіснуючого замовлення не має віддавати 500 (Stripe би ретраїв вічно)."""
    try:
        func(order_id, **kwargs)
    except Order.DoesNotExist:
        logger.warning("Вебхук Stripe для неіснуючого замовлення #%s", order_id)
