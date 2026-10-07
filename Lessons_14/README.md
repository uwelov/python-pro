# bookstore_project

Django-проєкт для домашнього завдання: перший крок на шляху до
повноцінного інтернет-магазину книг. Наступні завдання (views, forms,
DRF-API, авторизація тощо) будуть додаватись поверх цієї бази.

## Структура

```
bookstore_project/
├─ config/                  # налаштування проєкту (settings, urls, wsgi/asgi)
├─ catalog/                 # застосунок з моделями, views, формами, шаблонами
│  ├─ models.py
│  ├─ admin.py
│  ├─ apps.py               # реєстрація unicode-сумісної LIKE для SQLite
│  ├─ forms.py               # BookForm (ModelForm з Bootstrap-віджетами)
│  ├─ views.py               # 5 CBV: List/Detail/Create/Update/Delete + Category List
│  ├─ urls.py                 # URLconf застосунку, app_name="catalog"
│  ├─ migrations/
│  ├─ static/catalog/css/     # app-level статика (catalog.css)
│  ├─ templates/catalog/      # base.html, navbar, картки книг, форми, пагінація
│  └─ management/commands/
│     ├─ seed_demo_data.py     # наповнює базу тестовими даними
│     └─ demo_orm_queries.py   # демонструє filter/annotate/Q-запити
├─ static/css/               # project-level статика (project.css)
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

## Запуск

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo_data      # тестові категорії та книги
python manage.py demo_orm_queries    # приклади ORM-запитів у консоль

python manage.py runserver
```

Адмінка: `http://127.0.0.1:8000/admin/`
