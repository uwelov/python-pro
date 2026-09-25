# bookstore_project

Django-проєкт для домашнього завдання: перший крок на шляху до
повноцінного інтернет-магазину книг. Наступні завдання (views, forms,
DRF-API, авторизація тощо) будуть додаватись поверх цієї бази.

## Структура

```
bookstore_project/
├─ config/              # налаштування проєкту (settings, urls, wsgi/asgi)
├─ catalog/              # застосунок з моделями Category та Book
│  ├─ models.py
│  ├─ admin.py
│  ├─ apps.py            # реєстрація unicode-сумісної LIKE для SQLite
│  ├─ migrations/
│  └─ management/commands/
│     ├─ seed_demo_data.py     # наповнює базу тестовими даними
│     └─ demo_orm_queries.py   # демонструє filter/annotate/Q-запити
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
