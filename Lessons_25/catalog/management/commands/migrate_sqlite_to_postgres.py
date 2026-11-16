"""Одноразовий перенос даних зі старої бази SQLite в PostgreSQL.

Як це працює:
    1. читає дані зі "старої" бази (аліас `sqlite_legacy` у settings.py) через
       `dumpdata` у тимчасовий JSON-файл (UTF-8);
    2. записує їх у основну базу (`default` = PostgreSQL) через `loaddata`.

Службові таблиці, які Django створює сам при `migrate` (ContentType, Permission),
і тимчасові сесії не переносяться. Групи та права користувачів переносяться
через natural keys, тому не залежать від числових id.

Після `loaddata` Django автоматично скидає послідовності (sequences) PostgreSQL,
тож нові записи отримуватимуть id після найбільшого перенесеного.

Команду можна запускати повторно: записи з однаковими pk просто оновлюються.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connections

LEGACY_ALIAS = "sqlite_legacy"

EXCLUDED = [
    "contenttypes",
    "auth.permission",
    "sessions",
]


class Command(BaseCommand):
    help = "Переносить дані зі старого файлу SQLite у PostgreSQL (default)."

    def handle(self, *args, **options):
        if LEGACY_ALIAS not in settings.DATABASES:
            raise CommandError(
                "Аліас 'sqlite_legacy' не налаштовано: команда працює лише "
                "при DB_ENGINE=postgres."
            )

        legacy_path = Path(settings.DATABASES[LEGACY_ALIAS]["NAME"])
        if not legacy_path.is_file():
            raise CommandError(
                f"Файл SQLite не знайдено: {legacy_path}\n"
                "Покладіть свій db.sqlite3 у папку legacy/ (див. README)."
            )

        default_engine = connections["default"].vendor
        if default_engine != "postgresql":
            raise CommandError(f"Очікується PostgreSQL, а default — {default_engine}.")

        self._check_username_conflicts()

        self.stdout.write(f"Джерело:  {legacy_path}")
        self.stdout.write(f"Ціль:     PostgreSQL ({settings.DATABASES['default']['NAME']})\n")

        with tempfile.TemporaryDirectory() as tmp_dir:
            dump_file = Path(tmp_dir) / "legacy_dump.json"

            self.stdout.write("1/2 Експорт даних зі SQLite…")
            call_command(
                "dumpdata",
                database=LEGACY_ALIAS,
                natural_foreign=True,
                exclude=EXCLUDED,
                indent=2,
                output=str(dump_file),
            )
            size_kb = dump_file.stat().st_size / 1024
            self.stdout.write(f"    дамп: {size_kb:.1f} КБ")

            self.stdout.write("2/2 Імпорт даних у PostgreSQL…")
            call_command("loaddata", str(dump_file), database="default", verbosity=0)

        self.stdout.write(self.style.SUCCESS("\nПеренесено. Кількість записів у PostgreSQL:"))
        self._print_counts()

    def _check_username_conflicts(self) -> None:
        """Зупиняємось, якщо в PostgreSQL уже є користувач з тим самим username,
        але іншим id, ніж у SQLite — інакше loaddata впаде на унікальності."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        legacy = dict(User.objects.using(LEGACY_ALIAS).values_list("username", "pk"))
        existing = dict(User.objects.using("default").values_list("username", "pk"))
        conflicts = [
            name for name, pk in legacy.items() if name in existing and existing[name] != pk
        ]
        if conflicts:
            raise CommandError(
                "У PostgreSQL уже є користувачі з такими самими іменами, але іншими id: "
                + ", ".join(conflicts)
                + "\nНайчастіше це суперкористувач, створений при старті контейнера "
                "(DJANGO_SUPERUSER_*). Видаліть його або вимкніть змінні й повторіть."
            )

    def _print_counts(self) -> None:
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Group

        from catalog.models import Book, Category

        for label, model in [
            ("Користувачі", get_user_model()),
            ("Групи", Group),
            ("Категорії", Category),
            ("Книги", Book),
        ]:
            self.stdout.write(f"  {label}: {model.objects.using('default').count()}")
