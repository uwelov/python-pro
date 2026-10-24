"""Конфігурація застосунку catalog."""

from __future__ import annotations

import re

from django.apps import AppConfig
from django.db.backends.signals import connection_created


def _unicode_like(pattern: str, string: str) -> bool | None:
    """Регістронезалежна реалізація SQL LIKE з підтримкою Unicode (кирилиці).

    Стандартна SQLite LIKE регістронезалежна лише для ASCII-символів,
    тому пошук типу author__icontains="мартін" не знаходив "Мартін".
    Ця функція замінює вбудовану LIKE на варіант, що коректно працює
    з будь-яким алфавітом.
    """
    if pattern is None or string is None:
        return None
    regex = re.escape(pattern).replace("%", ".*").replace("_", ".")
    return re.fullmatch(regex, string, re.IGNORECASE | re.UNICODE) is not None


def _register_sqlite_unicode_like(sender, connection, **kwargs) -> None:
    if connection.vendor == "sqlite":
        # Django додає до LIKE ще й ESCAPE-символ (напр. LIKE ... ESCAPE '\'),
        # через що SQLite викликає 3-аргументну версію функції LIKE(x, y, escape),
        # а не 2-аргументну — тому реєструємо обидві.
        connection.connection.create_function("LIKE", 2, _unicode_like)
        connection.connection.create_function(
            "LIKE", 3, lambda pattern, string, escape: _unicode_like(pattern, string)
        )


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "catalog"

    def ready(self) -> None:
        connection_created.connect(_register_sqlite_unicode_like)
