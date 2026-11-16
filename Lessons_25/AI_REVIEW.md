# AI Code Review — «Книжковий магазин»

Документ описує, як AI (**Claude**, Anthropic, через чат) використано для покращення проєкту:
**(1)** code review трьох складних views, **(2)** генерація тестів для трьох моделей, **(3)** документація.
Промпти — в [`AI_PROMPTS.md`](AI_PROMPTS.md), звіти покриття — в [`reports/`](reports/).

> **Принцип роботи.** Рекомендації AI не приймалися «на віру»: кожну знахідку спершу **відтворено
> тестом на оригінальному коді** (тест падає), потім застосовано виправлення (тест проходить).
> Рекомендації, які не підійшли до нашого контексту, **відхилено з поясненням** — вони теж у документі.
> Тести-відтворювачі: [`tests/unit/test_review_regressions.py`](tests/unit/test_review_regressions.py).

## Зведення

| | До ревʼю | Після |
|---|---|---|
| Тестів у проєкті | 230 | **311** |
| Тести-відтворювачі знахідок | 16 з 18 падали | **18 з 18 проходять** |
| Покриття всього проєкту | 93% | **95%** |
| `catalog/models.py` / `orders/models.py` (лише AI-тести) | — | **100% / 100%** (поріг 60%) |
| Views/методи без docstring | 22 з 52 | **0 з 52** |
| Знахідок ревʼю | — | 18: **9 застосовано**, 4 відхилено, 5 відкладено |
| Додатково знайдено під час генерації тестів | — | відсутня валідація `Book.price` (виправлено) |

---

## 1. Code review трьох views

Вибрано три найскладніші місця за кількістю гілок, зовнішніх викликів і ризиком: **`CheckoutView.form_valid`**
(транзакція + зовнішній платіж + компенсації), **`stripe_webhook`** (безпека, ідемпотентність) та
**`BookListView`** (фільтри, пагінація).

Критерії, за якими AI переглядало код: коректність, **обробка помилок і компенсації**, **безпека**,
**конкурентність**, продуктивність, читабельність/тестованість.

### 1.1 `CheckoutView` (оформлення замовлення + оплата)

#### Оригінальний код

```python
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
```

#### Рекомендації AI

| # | Серйозність | Знахідка | Рішення |
|---|---|---|---|
| C1 | 🔴 висока | Компенсується лише збій Stripe (`StripeError`, `ImproperlyConfigured`). Будь-який інший виняток після `create_order` (БД, мережа, баг) залишає замовлення зі статусом «очікує оплати» **і з резервом книг на складі** — «витік складу». | ✅ **Застосовано**: `except Exception` → `cancel_order` → `raise` (виняток не ковтаємо). Тест: `test_unexpected_error_after_order_creation_releases_stock` |
| C2 | 🔴 висока | Неоплачені замовлення ніколи не закінчуються, якщо вебхук `checkout.session.expired` не налаштований (а в README він позначений як необов'язковий) або не дійшов: резерв висить вічно. | ✅ **Застосовано**: `services.cancel_stale_orders()` + команда `manage.py cancel_stale_orders` + сервіс `stale_orders` у `docker-compose.yml` (раз на 10 хв). 3 тести + тест команди |
| C3 | 🟡 середня | Подвійний клік по «Перейти до оплати» може створити два замовлення і два резерви. | ✅ **Застосовано** як пом'якшення: кнопка блокується після першого submit (`data-disable-on-submit`). Це **не** серверна ідемпотентність — див. C6 |
| C4 | 🟡 середня | Запропоновано загорнути `create_order` і створення Stripe-сесії в один `transaction.atomic`, щоб збій відкочувався автоматично. | ❌ **Відхилено.** `create_order` тримає `select_for_update` на рядках книг: мережевий виклик до Stripe всередині транзакції блокував би інші оформлення тих самих книг на секунди. А якщо процес впаде після створення сесії, але до коміту, лишиться платіжна сесія без замовлення. Правильний шаблон — **компенсація** (`cancel_order`), що й зроблено в C1 |
| C5 | 🟢 низька | Лист надсилається синхронно в запиті — додає затримку. | ⏳ **Відкладено**: потрібна черга завдань (Celery/RQ), поза обсягом проєкту. Збій пошти вже не ламає замовлення (`send_order_created_email` ловить помилки) |
| C6 | 🟢 низька | Для створення Stripe-сесії варто передавати `idempotency_key`, щоб мережеві ретраї не плодили сесії. | ⏳ **Відкладено**: сесія створюється раз на замовлення, ретраїв немає; повертаємось, якщо додамо автоматичні повтори |

#### Фінальний код

```python
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
        """Не пускає на оформлення з порожнім кошиком.

        Автентифікований користувач із порожнім кошиком отримує редірект на кошик з підказкою.
        Анонім іде далі в `LoginRequiredMixin` — спершу вхід, а потім уже перевірка кошика."""
        if request.user.is_authenticated and len(Cart(request)) == 0:
            messages.info(request, _("Кошик порожній — додайте книги перед оформленням."))
            return redirect("orders:cart-detail")
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        """Попередньо заповнює форму ім'ям та email з профілю користувача.

        Returns:
            Словник початкових значень для `CheckoutForm`."""
        user = self.request.user
        return {"full_name": user.get_full_name() or user.get_username(), "email": user.email}

    def get_context_data(self, **kwargs):
        """Додає в контекст склад кошика та суму для блоку «Ваше замовлення».

        Returns:
            Контекст шаблону з ключами `items` і `total_price`."""
        context = super().get_context_data(**kwargs)
        cart = Cart(self.request)
        context["items"] = list(cart)
        context["total_price"] = sum((i["total_price"] for i in context["items"]), 0)
        return context

    def form_valid(self, form):
        """Оформлює замовлення: Order (atomic) -> Stripe Checkout Session -> лист.

        Послідовність і компенсації:
            1. `create_order` резервує книги; нестача -> повідомлення й повернення в кошик.
            2. Створення Stripe-сесії. Збій платіжної системи або будь-яка інша помилка ->
               `cancel_order` повертає книги на склад (кошик лишається цілим).
            3. Лише після успіху: очищення кошика й лист «замовлення прийнято».

        Args:
            form: валідна `CheckoutForm` (ім'я, email, телефон).

        Returns:
            303-редірект на сторінку оплати Stripe; при збої — редірект назад."""
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
        except Exception:
            # Будь-який інший збій (БД, мережа, баг): замовлення вже створене і резервує книги,
            # тож компенсуємо — інакше воно «висітиме» неоплаченим. Виняток не ковтаємо.
            logger.exception("Неочікувана помилка під час оформлення замовлення #%s", order.pk)
            services.cancel_order(order.pk)
            raise

        cart.clear()
        # Лист «замовлення прийнято» — лише тепер, коли оплата реально ініційована.
        send_order_created_email(order.pk)
        return response
```

Супровідні зміни: `services.cancel_stale_orders` (нижче), команда `cancel_stale_orders`,
скрипт блокування кнопки в `orders/templates/orders/checkout.html`.

---

### 1.2 `stripe_webhook` (прийом подій платіжної системи)

#### Оригінальний код

```python
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
```

```python
@transaction.atomic
def mark_order_paid(
    order_id: int, *, session_id: str = "", payment_intent_id: str = ""
) -> bool:
    """Позначає замовлення оплаченим. Ідемпотентна: можна викликати з вебхука і зі сторінки успіху.

    Returns:
        True — статус змінено щойно; False — вже було оплачено або не можна оплатити.
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

    order.status = Order.Status.PAID
    order.paid_at = timezone.now()
    if session_id:
        order.stripe_session_id = session_id
    if payment_intent_id:
        order.stripe_payment_intent_id = payment_intent_id
    order.save()
    logger.info("Замовлення #%s оплачено", order.pk)
    return True
```

#### Рекомендації AI

| # | Серйозність | Знахідка | Рішення |
|---|---|---|---|
| W1 | 🔴 висока | Подія `completed` позначає замовлення оплаченим, **не звіряючи суму й валюту** із замовленням. Дані з вебхука (і зі сторінки успіху) не повинні довірятися «наосліп» — це defense in depth. | ✅ **Застосовано**: `mark_order_paid(..., amount_total, currency)` порівнює з сумою замовлення (`to_minor_units`); при розбіжності — `logger.error` і замовлення **не** оплачується. Працює і для вебхука, і для `order_success`. Тести (параметризовані: збіг / інша сума / інша валюта / поля відсутні) |
| W2 | 🟡 середня | `int(order_id)` на некоректних метаданих кидає `ValueError` → 500 → Stripe ретраїть подію **кілька днів** без шансу на успіх. | ✅ **Застосовано**: `_parse_order_id` повертає `None`, вебхук логує й відповідає 200. Тест: `test_webhook_with_malformed_order_id_does_not_crash` |
| W3 | 🟢 низька | Ланцюжок `if/elif` із дублюванням розбору `order_id`; додати нову подію незручно, окремо протестувати обробник неможливо. | ✅ **Застосовано**: таблиця обробників `_EVENT_HANDLERS` + малі функції `_handle_payment_succeeded`, `_handle_session_expired` |
| W4 | 🟢 низька | Зберігати id оброблених подій для дедуплікації. | ❌ **Відхилено**: обробники й так ідемпотентні (перевірка статусу під `select_for_update`), додаткова таблиця — зайва складність |
| W5 | 🟢 низька | Для неіснуючого замовлення віддавати 4xx. | ❌ **Відхилено**: 4xx/5xx змусять Stripe ретраїти даремно. Лишаємо 200 + warning у логах (тепер це описано в docstring) |
| W6 | 🟢 низька | Обробити `checkout.session.async_payment_failed`. | ⏳ **Відкладено**: картки — синхронні; додати разом із відкладеними методами оплати (SEPA тощо) |

Перевірено й залишено без змін (AI підтвердило коректність): підпис перевіряється по **сирому** тілу
(`request.body`) через `construct_webhook_event`; `csrf_exempt` виправданий (автентифікація — підписом);
`require_POST`; недійсний підпис/JSON → 400.

#### Фінальний код

```python
def _parse_order_id(session: dict) -> int | None:
    """Дістає id замовлення з metadata (або client_reference_id); None, якщо його немає чи він некоректний."""
    raw = (session.get("metadata") or {}).get("order_id") or session.get("client_reference_id")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _handle_payment_succeeded(order_id: int, session: dict) -> None:
    """checkout.session.completed / async_payment_succeeded: позначає замовлення оплаченим."""
    if session.get("payment_status") != "paid":
        return
    services.mark_order_paid(
        order_id,
        session_id=session.get("id") or "",
        payment_intent_id=str(session.get("payment_intent") or ""),
        amount_total=session.get("amount_total"),
        currency=session.get("currency"),
    )


def _handle_session_expired(order_id: int, session: dict) -> None:
    """checkout.session.expired: оплата не відбулась — скасовує замовлення й знімає резерв."""
    services.cancel_order(order_id)


_EVENT_HANDLERS = {
    "checkout.session.completed": _handle_payment_succeeded,
    "checkout.session.async_payment_succeeded": _handle_payment_succeeded,
    "checkout.session.expired": _handle_session_expired,
}


@csrf_exempt
@require_POST
def stripe_webhook(request: HttpRequest) -> HttpResponse:
    """Приймає події Stripe. CSRF вимкнено свідомо: автентифікація — за підписом Stripe.

    Відповіді: 400 — недійсний підпис/JSON (Stripe це ретраїть, і це правильно);
    200 — подію прийнято, у тому числі невідомого типу, з некоректним або неіснуючим
    замовленням (500 змусив би Stripe ретраїти подію днями без шансу на успіх).
    """
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
    handler = _EVENT_HANDLERS.get(event["type"])
    if handler is None:
        return HttpResponse(status=200)

    session = event["data"]["object"]
    order_id = _parse_order_id(session)
    if order_id is None:
        logger.warning("Вебхук Stripe %s без коректного order_id", event["type"])
        return HttpResponse(status=200)

    try:
        handler(order_id, session)
    except Order.DoesNotExist:
        logger.warning("Вебхук Stripe для неіснуючого замовлення #%s", order_id)
    return HttpResponse(status=200)
```

```python
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
```

---

### 1.3 `BookListView` (каталог: пошук, фільтри, пагінація)

#### Оригінальний код

```python
class BookListView(ListView):
    """Список книг із пошуком, фільтрами за категорією/наявністю та пагінацією.

    Доступний усім відвідувачам без автентифікації — перегляд каталогу
    не обмежується.
    """

    model = Book
    paginate_by = 6
    context_object_name = "books"

    def get_queryset(self) -> QuerySet[Book]:
        queryset = Book.objects.select_related("category").all()

        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) | Q(author__icontains=query)
            )

        category_slug = self.request.GET.get("category", "").strip()
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)

        stock_status = self.request.GET.get("stock", "").strip()
        if stock_status == "in_stock":
            queryset = queryset.filter(stock__gt=0)
        elif stock_status == "out_of_stock":
            queryset = queryset.filter(stock=0)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.annotate(book_count=Count("books"))
        context["current_query"] = self.request.GET.get("q", "")
        context["current_category"] = self.request.GET.get("category", "")
        context["current_stock"] = self.request.GET.get("stock", "")

        # querystring без 'page' — щоб пагінація зберігала активні фільтри
        params = self.request.GET.copy()
        params.pop("page", None)
        context["querystring"] = params.urlencode()
        return context
```

#### Рекомендації AI

| # | Серйозність | Знахідка | Рішення |
|---|---|---|---|
| B1 | 🟡 середня | `Meta.ordering = ["title"]` не унікальний: книги з однаковою назвою можуть мінятись місцями між запитами, і **пагінація дублює або губить записи**. | ✅ **Застосовано**: `order_by("title", "pk")`. Тест перевіряє SQL |
| B2 | 🟡 середня | Параметри `q/category/stock` парсяться двічі (у `get_queryset` і `get_context_data`), **не валідуються**, а сире значення потрапляє в контекст (`current_stock = "banana"`). | ✅ **Застосовано**: `BookFilterForm` (Django-форма) — очищення, ігнорування некоректних значень, метод `filter()`; view став коротшим. 6 тестів |
| B3 | 🟢 низька | Шаблон отримує очищені значення, а не сирий GET. | ✅ Наслідок B2 |
| B4 | 🟢 низька | `icontains` по неіндексованих колонках → повне сканування таблиці. | ⏳ **Відкладено**: для PostgreSQL — індекс `pg_trgm` (GIN) або `SearchVector`; на поточних обсягах не впливає |
| B5 | 🟢 низька | Анотація категорій (`Count`) на кожен запит — можна кешувати. | ⏳ **Відкладено** (кеш Redis уже є; додамо, коли з'являться метрики) |
| B6 | — | Замінити `ListView` на ручний `Paginator`. | ❌ **Відхилено**: жодної переваги, більше коду |

#### Фінальний код

```python
class BookListView(ListView):
    """Список книг із пошуком, фільтрами за категорією/наявністю та пагінацією.

    Доступний усім відвідувачам без автентифікації — перегляд каталогу
    не обмежується.
    """

    model = Book
    paginate_by = 6
    context_object_name = "books"

    @cached_property
    def filter_form(self) -> BookFilterForm:
        """Форма з параметрами фільтрації з query string (створюється один раз на запит)."""
        return BookFilterForm(self.request.GET)

    def get_queryset(self) -> QuerySet[Book]:
        """Книги з урахуванням фільтрів. Порядок `title, pk` — детермінований, тож пагінація
        не «дублює» й не губить книги з однаковою назвою між сторінками."""
        queryset = Book.objects.select_related("category")
        return self.filter_form.filter(queryset).order_by("title", "pk")

    def get_context_data(self, **kwargs):
        """Додає категорії для фільтра, поточні значення фільтрів і query string для пагінації."""
        context = super().get_context_data(**kwargs)
        values = self.filter_form.cleaned_values()
        context["categories"] = Category.objects.annotate(book_count=Count("books"))
        context["current_query"] = values["q"]
        context["current_category"] = values["category"]
        context["current_stock"] = values["stock"]

        # querystring без 'page' — щоб пагінація зберігала активні фільтри
        params = self.request.GET.copy()
        params.pop("page", None)
        context["querystring"] = params.urlencode()
        return context
```

```python
class BookFilterForm(forms.Form):
    """Валідація параметрів фільтрації каталогу (?q=, ?category=, ?stock=) з GET-запиту.

    Некоректні значення (напр. ?stock=banana) тихо ігноруються і не потрапляють ні у фільтр,
    ні в контекст шаблону. Логіка фільтрації живе тут, а не у view, тож її можна тестувати окремо.
    """

    q = forms.CharField(required=False, strip=True)
    category = forms.CharField(required=False, strip=True)
    stock = forms.ChoiceField(
        required=False,
        choices=[("in_stock", _("В наявності")), ("out_of_stock", _("Немає в наявності"))],
    )

    def cleaned_values(self) -> dict[str, str]:
        """Очищені значення всіх полів; для відсутніх або некоректних — порожній рядок."""
        self.is_valid()  # заповнює cleaned_data валідними полями; помилок не піднімає
        return {name: self.cleaned_data.get(name, "") for name in self.fields}

    def filter(self, queryset: QuerySet) -> QuerySet:
        """Застосовує очищені параметри до QuerySet книг."""
        values = self.cleaned_values()
        if values["q"]:
            queryset = queryset.filter(
                Q(title__icontains=values["q"]) | Q(author__icontains=values["q"])
            )
        if values["category"]:
            queryset = queryset.filter(category__slug=values["category"])
        if values["stock"] == "in_stock":
            queryset = queryset.filter(stock__gt=0)
        elif values["stock"] == "out_of_stock":
            queryset = queryset.filter(stock=0)
        return queryset
```

---

### 1.4 Докази: тести-відтворювачі

На **оригінальному** коді (до виправлень) результат: `16 failed, 2 passed` — два пройдені тести
фіксують поведінку, яку виправлення не мало зламати.

```text
FAILED test_unexpected_error_after_order_creation_releases_stock
FAILED test_stale_pending_orders_are_cancelled_and_stock_released
FAILED test_stale_cancellation_ignores_paid_orders
FAILED test_cancel_stale_orders_command
FAILED test_checkout_form_disables_submit_button_against_double_click
FAILED test_webhook_with_malformed_order_id_does_not_crash
FAILED test_webhook_verifies_amount_and_currency[100-uah-False]
FAILED test_webhook_verifies_amount_and_currency[45000-usd-False]
FAILED test_success_page_does_not_trust_mismatched_amount
FAILED test_book_list_queryset_has_deterministic_ordering
FAILED test_book_list_sanitizes_unknown_filter_values
FAILED test_book_filter_form_cleaning[params0-expected0]
FAILED test_book_filter_form_cleaning[params1-expected1]
FAILED test_book_filter_form_cleaning[params2-expected2]
FAILED test_book_filter_form_cleaning[params3-expected3]
FAILED test_book_filter_form_filters_queryset
```

Після застосування рекомендацій: **18 passed**; весь набір: **311 passed**.

---

## 2. Генерація тестів для моделей (AI)

**Моделі:** `Category`, `Book`, `Order` (разом з `OrderItem`) — файл
[`tests/ai_generated/test_ai_models.py`](tests/ai_generated/test_ai_models.py), 55 тестів.
Кожен тест містить коментар `# Generated with AI, reviewed and modified` (це перевіряє останній
тест файлу). Фабрики — `factory-boy` (`tests/factories.py`).

### Як це відбувалось

1. **Чернетка від AI** — 53 тести: `__str__`, властивості, валідація (`full_clean`), обмеження БД, зв'язки й
   `on_delete`, `Meta.ordering`, переклади `verbose_name`, точність `Decimal`, кількість SQL-запитів.
2. **Запуск** — усі 53 пройшли з першого разу. Це **не** доказ якості, тому далі — ревʼю.
3. **Ревʼю чернетки (що змінено вручну):**
   - тест `valid_slugs` містив гілку `if/else` і суперечливий коментар → розбито на два прості тести;
   - тест `quantity_must_be_positive` змішував перевірку валідатора і БД → розбито на два;
   - тест `-0.01` для ціни **не проходив би** на тодішній моделі — і виявилось, що **`Book.price` не
     має жодної валідації: від'ємна ціна проходила і через модель, і через `BookForm`**.
4. **Виправлення моделі** (знахідка AI-тестів): `MinValueValidator(0)` на `price` + `CheckConstraint(price >= 0)`
   (бо валідатори не спрацьовують при `.save()`), міграція `catalog/migrations/0003_*`.
5. **Мутаційна перевірка** — штучно ламаємо код моделей і дивимось, чи тести це помічають:

```text
KILLED     Book.in_stock: > -> >=
KILLED     OrderItem.get_cost: * -> +
KILLED     Order.get_total_cost: ігнорує кількість
KILLED     Order.is_paid: PAID -> PENDING
KILLED     Book.Meta.ordering reversed
KILLED     Order.Meta.ordering reversed
KILLED     Book.price: прибрано валідатор
KILLED     Book.created_by: SET_NULL -> CASCADE
KILLED     Order.get_absolute_url
KILLED     Book.get_absolute_url
KILLED     Order.is_pending: PENDING -> PAID
KILLED     Book.__str__ без автора
KILLED     Order.user: SET_NULL -> CASCADE
KILLED     Order.status default PENDING -> PAID

Mutation score: 14/14
```

### Покриття (звіт: [`reports/coverage_models.txt`](reports/coverage_models.txt))

Запуск лише AI-тестів моделей, лише модулі `catalog.models` та `orders.models`, з гілками:

| Модуль | Рядків | Пропущено | Покриття |
|---|---|---|---|
| `catalog/models.py` | 37 | 0 | **100%** |
| `orders/models.py` | 55 | 0 | **100%** |

Вимога завдання — ≥ 60%. Повний звіт по проєкту: **94.5%**
([`reports/coverage_full.txt`](reports/coverage_full.txt), HTML — `reports/html_full/index.html`).

---

## 3. Документація

- **Docstrings для всіх views.** Аудит AST: з 52 об'єктів (класи, функції, методи у
  `catalog/views.py`, `catalog/async_views.py`, `orders/views.py`, `accounts/views.py`, `config/health.py`)
  **22 були без docstring**. AI згенерувало всі; ревʼю виправило два тексти (нечіткий опис
  `CheckoutView.dispatch`; короткі docstring у `order_pay`/`order_success`, які знайшов тест-сторож).
  Формат — Google style (`Args:` / `Returns:` / `Raises:`).
- **Тест-сторож** `tests/unit/test_docstrings.py` не дає docstring зникнути: перевіряє наявність
  у кожному view та `Args/Returns` у публічних функціях-views.
- **README** оновлено за допомогою AI (актуальний огляд проєкту, нові розділи, секція **AI Usage**).

---

## 4. Висновки: що AI зробило добре, а де помилялось

- ✅ Швидко знайшло **класи проблем**, які легко пропустити: «витік складу» при нетиповому винятку,
  вічний резерв без вебхука, довіру до даних із вебхука, нестабільну пагінацію.
- ✅ Згенерувало повні набори тестів і docstrings, які після невеликої правки пройшли перевірку.
- ⚠️ **Частину порад довелось відхилити**: «загорнути все в одну транзакцію» (C4) шкідлива для блокувань;
  «зберігати id подій» (W4) і «4xx для невідомого замовлення» (W5) — зайве або шкідливе в нашому контексті.
  Поради AI слід оцінювати на конкретному коді, а не застосовувати механічно.
- ⚠️ **Зелені тести чернетки ≠ якісні тести**: перша версія містила гілки в тестах; якість підтвердила
  лише мутаційна перевірка (14/14).
- ⚠️ Усе, що не перевірено тестом, залишається припущенням: тому кожна знахідка має відтворювач, а
  відкладені (⏳) пункти чесно позначені такими.
