# bookstore_project

Django-проєкт для домашнього завдання: перший крок на шляху до
повноцінного інтернет-магазину книг. Наступні завдання (views, forms,
DRF-API, авторизація тощо) будуть додаватись поверх цієї бази.

## Структура

```
bookstore_project/
├─ config/                  # налаштування проєкту (settings, urls, wsgi/asgi)
│  ├─ settings.py            # env-конфігурація, PostgreSQL/SQLite, Redis, WhiteNoise
│  ├─ urls.py
│  ├─ health.py               # /health/ — перевірка БД і Redis (для healthcheck)
│  └─ middleware.py           # власний RequestLoggingMiddleware
├─ accounts/                 # застосунок автентифікації
│  ├─ models.py               # кастомна модель User (AbstractUser + phone_number)
│  ├─ forms.py                 # RegisterForm, LoginForm (Bootstrap-віджети)
│  ├─ views.py                  # RegisterView, LoginView, LogoutView
│  ├─ urls.py                    # app_name="accounts"
│  ├─ admin.py
│  ├─ templates/accounts/         # login.html, register.html
│  └─ management/commands/
│     └─ setup_groups.py           # створює групи "Бібліотекарі"/"Клієнти"
├─ orders/                  # кошик, замовлення, оплата Stripe
│  ├─ models.py               # Order, OrderItem
│  ├─ cart.py                  # Cart (session): add / remove / clear
│  ├─ services.py              # create_order (transaction.atomic), cancel_order, mark_order_paid
│  ├─ payments.py              # Stripe Checkout Session, перевірка підпису вебхука
│  ├─ emails.py                # лист «замовлення прийнято»
│  ├─ views.py, urls.py        # кошик, checkout, success, вебхук (app_name="orders")
│  ├─ admin.py                 # Order + inline OrderItem
│  ├─ templates/orders/        # кошик, checkout, мої замовлення, шаблони листів
│  └─ tests.py                 # 53 тести (разом з іншими застосунками)
├─ catalog/                 # застосунок з моделями, views, формами, шаблонами
│  ├─ models.py               # Category, Book (+ created_by → User)
│  ├─ admin.py
│  ├─ apps.py                  # реєстрація unicode-сумісної LIKE для SQLite
│  ├─ forms.py                  # BookForm (ModelForm з Bootstrap-віджетами)
│  ├─ views.py                   # 5 CBV + перевірка прав (permissions)
│  ├─ urls.py                     # URLconf застосунку, app_name="catalog"
│  ├─ migrations/
│  ├─ static/catalog/css/         # app-level статика (catalog.css)
│  ├─ templates/catalog/          # base.html, navbar, картки книг, форми, пагінація
│  └─ management/commands/
│     ├─ seed_demo_data.py         # наповнює базу тестовими даними
│     └─ demo_orm_queries.py       # демонструє filter/annotate/Q-запити
├─ static/css/               # project-level статика (project.css)
├─ legacy/                   # сюди кладеться старий db.sqlite3 для переносу в PostgreSQL
├─ logs/                     # app.log, requests.log (створюються автоматично)
├─ Dockerfile
├─ docker-compose.yml        # web + db (PostgreSQL) + redis
├─ docker-entrypoint.sh      # очікування БД, міграції, collectstatic, групи
├─ .env / .env.example       # змінні оточення (.env не комітиться)
├─ manage.py
└─ requirements.txt
```

## Моделі

**Category** (`catalog/models.py`)
- `name` — назва категорії (унікальна)
- `slug` — слаг для URL (унікальний)

**Book**
- `title`, `author` — назва та автор
- `price` — ціна (`DecimalField`)
- `description` — опис (необов'язковий)
- `stock` — кількість на складі
- `category` — `ForeignKey` на `Category` (`related_name="books"`)
- `created_at` — дата додавання (проставляється автоматично)
- властивість `in_stock` — чи є книга в наявності (`stock > 0`)

## Адмін-панель (`catalog/admin.py`)

- **CategoryAdmin**
  - інлайн `BookInline` — книги категорії редагуються прямо на її сторінці
  - `list_display` показує кількість книг у категорії (через `annotate`)
  - пошук за назвою/слагом, автозаповнення слага з назви (`prepopulated_fields`)
- **BookAdmin**
  - `list_filter`: за категорією та власним фільтром **"наявність на складі"**
    (`StockStatusFilter` — showcase `SimpleListFilter`)
  - `search_fields`: назва, автор, опис
  - `list_editable`: ціну й кількість можна редагувати прямо у списку
  - `autocomplete_fields` для категорії (працює завдяки `search_fields` у `CategoryAdmin`)

## ORM-запити (`catalog/management/commands/demo_orm_queries.py`)

Демонструє:
1. `filter()` з кількома умовами (`stock__gt`, `price__lt`)
2. `filter()` через зв'язок (`category__slug`)
3. `Q`-об'єкти з `|` (АБО) — пошук за назвою або автором
4. `Q`-об'єкти з `&` та `~` (І, НЕ) — комбінований фільтр
5. `annotate()` з `Count` і `Avg` — статистика по категоріях
6. `annotate()` з умовним `Count(..., filter=Q(...))` — категорії з відсутніми книгами

### Про SQLite та кирилицю

SQLite за замовчуванням регістронезалежний `LIKE` робить лише для
ASCII-символів, тому `icontains` з кирилицею (наприклад, `"мартін"`)
без додаткових налаштувань нічого не знаходив. У `catalog/apps.py`
зареєстровано власну реалізацію SQL-функції `LIKE` на основі
`re.IGNORECASE | re.UNICODE`, яка коректно працює з будь-яким алфавітом.
Для PostgreSQL/MySQL цей обхідний шлях не потрібен — вони й так
регістронезалежні для Unicode за замовчуванням (залежно від колації).

## Class-Based Views та URL (`catalog/views.py`, `catalog/urls.py`)

Усі URL підключені через `catalog/urls.py` з `app_name = "catalog"`
(namespace), тому в шаблонах і коді вони викликаються як
`{% url 'catalog:book-list' %}`, `reverse('catalog:book-detail', ...)` тощо.

| View | URL | name |
|---|---|---|
| `BookListView` | `/` | `catalog:book-list` |
| `BookDetailView` | `/books/<pk>/` | `catalog:book-detail` |
| `BookCreateView` | `/books/add/` | `catalog:book-create` |
| `BookUpdateView` | `/books/<pk>/edit/` | `catalog:book-update` |
| `BookDeleteView` | `/books/<pk>/delete/` | `catalog:book-delete` |
| `CategoryListView` | `/categories/` | `catalog:category-list` |

**BookListView** вміє одночасно:
- пошук за назвою/автором (`?q=...`, через `Q`-об'єкти)
- фільтр за категорією (`?category=<slug>`)
- фільтр за наявністю (`?stock=in_stock` / `out_of_stock`)
- пагінацію (`paginate_by = 6`), яка зберігає активні фільтри в
  посиланнях "Далі"/"Назад" (через `querystring` у контексті)

**BookCreateView** / **BookUpdateView** використовують спільний шаблон
`book_form.html` (обидва за замовчуванням рендерять `<model>_form.html`)
і спільну форму `BookForm`. Після збереження показується
flash-повідомлення (`django.contrib.messages`) і редирект на деталі книги
(`get_absolute_url`).

**BookDeleteView** показує сторінку підтвердження і після POST редиректить
на список книг.

## Шаблони та Bootstrap (`catalog/templates/catalog/`)

- `base.html` — спільний каркас: Bootstrap 5 (CDN), navbar з посиланнями
  на "Книги"/"Категорії"/"+ Додати книгу", блок для flash-повідомлень,
  footer. Підключає і app-level (`catalog/css/catalog.css`), і
  project-level (`css/project.css`) статику.
- `book_list.html` — форма фільтрів (GET) + сітка карток книг
  (Bootstrap `card`, `row-cols-*`) + `{% include "catalog/_pagination.html" %}`
- `_pagination.html` — перевикористовуваний партial пагінації
  (Bootstrap `pagination`), зберігає `?q=`, `?category=`, `?stock=` при
  переході між сторінками
- `book_detail.html` — хлібні крихти, картка з повною інформацією,
  кнопки "Редагувати"/"Видалити"
- `book_form.html` — єдина форма для створення й редагування (перевіряє
  `{% if object %}` для заголовка та кнопки "Скасувати")
- `book_confirm_delete.html` — підтвердження видалення
- `category_list.html` — список категорій з кількістю книг (`annotate`),
  кожна веде на відфільтрований список книг

## Статичні файли (`config/settings.py`)

- `STATIC_URL = 'static/'`
- `STATICFILES_DIRS = [BASE_DIR / 'static']` — project-level статика
  (напр. `static/css/project.css`), що не прив'язана до конкретного застосунку
- `STATIC_ROOT = BASE_DIR / 'staticfiles'` — куди `collectstatic` збере
  файли для продакшну
- app-level статика (`catalog/static/catalog/css/catalog.css`)
  підхоплюється автоматично завдяки `django.contrib.staticfiles` в
  `INSTALLED_APPS` — окремо нічого реєструвати не треба

## Авторизація (застосунок `accounts`)

### Custom User Model

`accounts.User` успадковує `AbstractUser` і додає поле `phone_number`.
`AUTH_USER_MODEL = 'accounts.User'` виставлено в `settings.py` **до**
першої міграції — підмінити модель користувача після того, як міграції
з FK на стандартний `auth.User` вже застосовані до бази, Django не
дозволяє.

Модель `Book` має `created_by` (`FK` на `settings.AUTH_USER_MODEL`,
`null=True, blank=True, on_delete=SET_NULL`) — показує, хто додав книгу,
і використовується для демонстрації зв'язку User ↔ бізнес-модель.

### Реєстрація / логін / логаут

| Що | URL | name |
|---|---|---|
| Реєстрація | `/accounts/register/` | `accounts:register` |
| Логін | `/accounts/login/` | `accounts:login` |
| Логаут | `/accounts/logout/` (лише POST) | `accounts:logout` |

- `RegisterView` — `CreateView` на основі `RegisterForm`
  (`UserCreationForm` + обов'язковий email і необов'язковий телефон),
  після успішної реєстрації одразу логінить користувача.
- `LoginView`/`LogoutView` — обгортки над стандартними
  `django.contrib.auth.views`, зі своїм шаблоном і Bootstrap-формою.
  Логаут приймає лише `POST` (вимога Django з 5.0+), тому в navbar це
  кнопка всередині `<form>`, а не звичайне посилання.
- `LOGIN_URL`, `LOGIN_REDIRECT_URL`, `LOGOUT_REDIRECT_URL` налаштовані
  в `settings.py`.

### Permissions та Groups

Команда `setup_groups` створює дві групи на основі стандартних
Django-прав моделі `Book`:

| Група | Права |
|---|---|
| **Бібліотекарі** | `add_book`, `change_book`, `delete_book`, `view_book` |
| **Клієнти** | `view_book` |

```bash
python manage.py setup_groups
```

`BookCreateView`/`BookUpdateView`/`BookDeleteView` захищені
`LoginRequiredMixin` + `PermissionRequiredMixin`
(`permission_required = "catalog.add_book"` тощо). Завдяки тому, як
Django реалізує `AccessMixin.handle_no_permission()`, **без**
`raise_exception = True` вже працює правильно:
- анонімний користувач → редирект на `/accounts/login/?next=...`
- автентифікований, але без потрібного права → `403 Forbidden`

(Якщо виставити `raise_exception = True` вручну на в'юсі — цей атрибут
спільний для обох міксинів, і анонімні користувачі теж почнуть
отримувати 403 замість редиректу на логін. Перевірено на практиці —
саме тому в коді цього атрибута немає.)

У шаблонах кнопки "Додати книгу"/"Редагувати"/"Видалити" ховаються,
якщо в поточного користувача немає відповідного права
(`{% if perms.catalog.add_book %}` тощо).

## Django Debug Toolbar

Підключено в `INSTALLED_APPS`/`MIDDLEWARE` і активний лише при
`DEBUG = True`. URL `/__debug__/` домонтовується умовно в
`config/urls.py`. `INTERNAL_IPS = ['127.0.0.1']` — тулбар показується
лише при зверненні з localhost.

## Логування (`LOGGING` у `settings.py`)

- `logs/app.log` — загальний лог застосунку (Django + `catalog` +
  `accounts`): створення/оновлення/видалення книг, реєстрації, логіни.
- `logs/requests.log` — окремий лог усіх HTTP-запитів від власного
  middleware (нижче).
- Обидва файли — `RotatingFileHandler` (1 МБ, 3 бекапи), плюс дублювання
  в консоль. Папка `logs/` створюється автоматично при старті
  (`LOGS_DIR.mkdir(exist_ok=True)`), у git не комітиться.

## Власний middleware (`config/middleware.py`)

`RequestLoggingMiddleware` логує кожен запит: метод, повний шлях,
статус-код відповіді, тривалість обробки в мс та ім'я користувача
(або `anonymous`). Приклад рядка логу:

```
INFO config.middleware: POST /books/add/ -> 302 (24.5 ms) [user=librarian]
```

Middleware підключено після `AuthenticationMiddleware` (щоб
`request.user` уже був доступний) і перед Debug Toolbar.

## Тестові користувачі (для ручної перевірки)

Після `migrate` і `setup_groups` можна створити:

```bash
python manage.py shell -c "
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
User = get_user_model()

librarian = User.objects.create_user('librarian', password='librarian12345')
librarian.groups.add(Group.objects.get(name='Бібліотекарі'))

customer = User.objects.create_user('customer', password='customer12345')
customer.groups.add(Group.objects.get(name='Клієнти'))
"
```

Перевірено вручну: анонім при спробі `/books/add/` отримує редирект на
логін; `customer` при тій самій спробі отримує `403`; `librarian`
успішно створює книгу, і в неї коректно проставляється `created_by`.

## Кошик, замовлення та оплата (застосунок `orders`)

### Моделі

- **Order** — `user`, `full_name`, `email`, `phone`, `status` (`pending` / `paid` / `cancelled`),
  `stripe_session_id`, `stripe_payment_intent_id`, `created_at`, `updated_at`, `paid_at`;
  метод `get_total_cost()`.
- **OrderItem** — `order` (FK, `related_name="items"`), `book` (FK, `SET_NULL`), `book_title`, `price`,
  `quantity`. Назва й ціна **копіюються** в рядок на момент замовлення, тож історія не змінюється,
  якщо книгу потім подорожчає, перейменують чи видалять. Є `CheckConstraint(quantity >= 1)`.

### Кошик (`orders/cart.py`)

Клас `Cart(request)` зберігає в `request.session` лише `{id_книги: кількість}` (ціни завжди беруться
з БД). Методи: `add(book, quantity, override_quantity)` (кількість обмежується залишком на складі),
`remove(book)`, `clear()`, а також `__iter__`, `__len__`, `get_total_price()`. Лічильник у navbar
доступний усюди через context processor. Дії з кошиком — лише POST (з CSRF); `?next=` перевіряється
проти open redirect.

### Створення замовлення в `transaction.atomic` (`orders/services.py`)

`create_order()` в одній транзакції: блокує рядки книг (`select_for_update`, порядок за pk — без
deadlock), перевіряє залишок, створює `Order` + `OrderItem` і зменшує `Book.stock`. Якщо хоча б однієї
книги бракує — **відкочується все** (ні замовлення, ні списань). Перевірено тестом на PostgreSQL: два
одночасні замовлення на останній примірник завершуються так, що проходить рівно одне; без
`select_for_update` цей тест падає (обидва проходять).

### Stripe Checkout

1. `/orders/checkout/` (потрібен вхід): форма контактів -> `create_order` -> `stripe.checkout.Session.create`
   -> редірект 303 на сторінку оплати Stripe. Кошик очищається лише після успішного створення сесії;
   якщо Stripe недоступний, замовлення скасовується, книги повертаються на склад, кошик лишається.
2. Після оплати Stripe повертає клієнта на `/orders/<id>/success/?session_id=...`. Статус перевіряється
   **запитом до Stripe**, а не довірою до параметра URL.
3. Паралельно Stripe шле вебхук `POST /stripe/webhook/`: `checkout.session.completed` -> замовлення
   `paid`; `checkout.session.expired` -> замовлення скасовується, склад відновлюється. Підпис
   перевіряється через `STRIPE_WEBHOOK_SECRET`. Обидва канали ідемпотентні.
4. Неоплачене замовлення можна оплатити повторно (`Оплатити зараз`) або скасувати на сторінці замовлення.

**Налаштування (тестовий режим):**

1. Створіть акаунт на stripe.com, у Dashboard (режим *Test*) візьміть `sk_test_...` і `pk_test_...`.
2. Впишіть їх у `.env` (`STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`), потім `docker compose up -d`.
3. Тестова картка: `4242 4242 4242 4242`, будь-яка майбутня дата, будь-який CVC.
4. Вебхук (необов'язково для демо, бо success-сторінка теж перевіряє оплату): встановіть
   [Stripe CLI](https://stripe.com/docs/stripe-cli) і виконайте
   `stripe listen --forward-to localhost:8000/stripe/webhook/` — він виведе `whsec_...`,
   впишіть його в `STRIPE_WEBHOOK_SECRET`.

Валюта — `STRIPE_CURRENCY` (за замовчуванням `uah`); суми беруться з цін книг без конвертації. Якщо
Stripe відхилить валюту для вашого акаунта, поставте `usd` або `eur`.

### Email

Після успішного оформлення (коли платіжну сесію створено) клієнту йде лист (текст + HTML) зі складом
замовлення. Сервіс `create_order` за замовчуванням ставить лист у `transaction.on_commit`, тобто він
надсилається лише після коміту (при відкаті листа немає); у потоці оформлення з оплатою лист
надсилається вже після створення Stripe-сесії, щоб клієнт не отримував лист про замовлення, яке
одразу скасувалось. Збій SMTP логується і не ламає замовлення.

Django 6.1 налаштовує пошту через `MAILERS` (старі `EMAIL_*` застаріли). Без `EMAIL_HOST` у `.env`
листи друкуються в консоль (`docker compose logs web`); для реальної відправки задайте
`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`.

### Адмінка

`OrderAdmin` з `OrderItemInline` (книга через autocomplete, ціна, кількість, сума рядка), фільтри за
статусом і датою, пошук за номером/email/ім'ям/користувачем, сума замовлення рахується в БД одним запитом.

### Тести

```bash
# локально (SQLite; у PowerShell: $env:DB_ENGINE="sqlite")
DB_ENGINE=sqlite python manage.py test
# або в Docker (PostgreSQL)
docker compose exec web python manage.py test
```

Охоплено: кошик, створення замовлення і відкат, лист лише після коміту, конкурентні замовлення,
Stripe-потік (виклики до Stripe замокано), вебхук з **реальним HMAC-підписом**, права доступу, адмінка.
Під час тестів Redis не потрібен.

## Docker (docker-compose)

Три сервіси (`docker-compose.yml`):

| Сервіс | Образ | Призначення | Volume | Healthcheck |
|---|---|---|---|---|
| `web` | збирається з `Dockerfile` | Django + gunicorn, порт 8000 | `static_volume` → `/app/staticfiles` | HTTP-запит до `/health/` (перевіряє БД і Redis) |
| `db` | `postgres:16` | PostgreSQL | `postgres_data` → дані БД | `pg_isready` |
| `redis` | `redis:7-alpine` | кеш і сесії | `redis_data` → `/data` | `redis-cli ping` |

`web` стартує лише коли `db` і `redis` у стані `healthy`
(`depends_on: condition: service_healthy`).

### Швидкий старт

```bash
docker compose up --build
```

Сайт: http://localhost:8000/ · Адмінка: http://localhost:8000/admin/ ·
Health: http://localhost:8000/health/

Файл `.env` уже є в проєкті (значення для розробки). Для чистого старту
розкоментуйте в ньому `DJANGO_SUPERUSER_*` — адмін створиться автоматично;
або створіть вручну:

```bash
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py seed_demo_data   # тестові книги
```

Корисні команди: `docker compose logs -f web` · `docker compose ps`
(колонка STATUS показує healthy) · `docker compose down` (дані зберігаються)
· `docker compose down -v` (видалити й дані).

### docker-entrypoint.sh

При кожному старті контейнера `web`: (1) чекає на PostgreSQL, (2) виконує
`migrate`, (3) `collectstatic` у volume, (4) за `SETUP_GROUPS=1` — `setup_groups`,
(5) якщо задано `DJANGO_SUPERUSER_*` — створює суперкористувача, і лише потім
запускає gunicorn (`exec "$@"`). Тобто міграції застосовуються автоматично.

### Змінні оточення (`.env`)

`settings.py` читає їх через `django-environ`: `SECRET_KEY`, `DEBUG`,
`ALLOWED_HOSTS`, `DB_ENGINE` (`postgres`/`sqlite`), `POSTGRES_*`, `REDIS_URL`.
У `docker-compose.yml` для `web` значення `POSTGRES_HOST`/`REDIS_URL`
перевизначені на імена сервісів (`db`, `redis`). Без `DB_ENGINE=postgres`
проєкт працює на SQLite, як раніше. `.env` — у `.gitignore`; шаблон — `.env.example`.

Redis використовується як кеш (`django.core.cache.backends.redis`) і для
сесій (`cached_db`). Статику віддає WhiteNoise. Debug Toolbar вмикається
лише при `DEBUG=True`.

### Перенесення даних SQLite → PostgreSQL

1. Покладіть свій `db.sqlite3` у папку `legacy/` (на ній схема має бути
   актуальною, тобто на ній раніше виконувався `python manage.py migrate`).
2. Запустіть `docker compose up -d` (БД вже мігрована entrypoint-ом).
3. Виконайте:

```bash
docker compose exec web python manage.py migrate_sqlite_to_postgres
```

Команда робить `dumpdata` зі SQLite (аліас `sqlite_legacy`) у тимчасовий
UTF-8 JSON і `loaddata` у PostgreSQL. `ContentType`, `Permission` та сесії
не переносяться (Django створює їх сам), групи й права користувачів
переносяться через natural keys. Sequences PostgreSQL скидаються
автоматично, тож нові записи не конфліктують за id. Команду можна
запускати повторно. Якщо в PostgreSQL уже є користувач з таким самим
іменем, але іншим id (типово — суперкористувач із `DJANGO_SUPERUSER_*`),
команда зупиниться з поясненням, нічого не змінивши.

Перенесення робиться всередині контейнера, тому не залежить від Windows:
дамп створюється в UTF-8 (у PowerShell `>` дав би UTF-16 і зламав би кирилицю).

## Запуск без Docker (SQLite)

> У `.env` за замовчуванням `DB_ENGINE=postgres` (для Docker). Щоб запускати
> проєкт локально на SQLite, змініть там на `DB_ENGINE=sqlite`.


```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser
python manage.py setup_groups         # групи "Бібліотекарі"/"Клієнти" + права
python manage.py seed_demo_data       # тестові категорії та книги
python manage.py demo_orm_queries     # приклади ORM-запитів у консоль

python manage.py runserver
```

Адмінка: `http://127.0.0.1:8000/admin/`
Сайт: `http://127.0.0.1:8000/`
Debug Toolbar: панель праворуч на будь-якій сторінці при `DEBUG=True`
