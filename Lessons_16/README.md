# bookstore_project

Django-проєкт для домашнього завдання: перший крок на шляху до
повноцінного інтернет-магазину книг. Наступні завдання (views, forms,
DRF-API, авторизація тощо) будуть додаватись поверх цієї бази.

## Структура

```
bookstore_project/
├─ config/                  # налаштування проєкту (settings, urls, wsgi/asgi)
│  ├─ settings.py            # AUTH_USER_MODEL, LOGGING, Debug Toolbar тощо
│  ├─ urls.py
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
├─ logs/                     # app.log, requests.log (створюються автоматично)
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

## Запуск

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
