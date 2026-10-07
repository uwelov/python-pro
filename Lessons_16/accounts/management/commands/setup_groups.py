"""Створює стандартні групи користувачів із правами на модель Book."""

from __future__ import annotations

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from catalog.models import Book

GROUPS_PERMISSIONS = {
    "Бібліотекарі": ["add_book", "change_book", "delete_book", "view_book"],
    "Клієнти": ["view_book"],
}


class Command(BaseCommand):
    help = (
        "Створює групи 'Бібліотекарі' (повний CRUD на книги) та "
        "'Клієнти' (лише перегляд) із відповідними правами на Book."
    )

    def handle(self, *args, **options):
        book_content_type = ContentType.objects.get_for_model(Book)

        for group_name, codenames in GROUPS_PERMISSIONS.items():
            group, created = Group.objects.get_or_create(name=group_name)
            permissions = Permission.objects.filter(
                content_type=book_content_type, codename__in=codenames
            )
            group.permissions.set(permissions)

            status = "створено" if created else "оновлено"
            self.stdout.write(
                self.style.SUCCESS(
                    f"Групу «{group_name}» {status}, "
                    f"призначено прав: {permissions.count()}"
                )
            )

        self.stdout.write(self.style.SUCCESS("\nГотово."))
