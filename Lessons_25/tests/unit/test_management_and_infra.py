"""Тести management-команд, middleware та SQLite-заміни LIKE."""

from io import StringIO
from unittest import mock

import pytest
from django.contrib.auth.models import Group
from django.core.management import CommandError, call_command
from django.db import connection
from django.http import HttpResponse
from django.test import RequestFactory

from accounts.models import User
from catalog.apps import _unicode_like
from catalog.models import Book, Category
from config.middleware import RequestLoggingMiddleware
from tests.factories import BookFactory

pytestmark = pytest.mark.django_db


def run(*args):
    out = StringIO()
    call_command(*args, stdout=out)
    return out.getvalue()


def test_setup_groups_creates_groups_with_permissions_and_is_idempotent():
    run("setup_groups"), run("setup_groups")
    assert Group.objects.get(name="Бібліотекарі").permissions.count() == 4
    assert Group.objects.get(name="Клієнти").permissions.count() == 1
    assert Group.objects.count() == 2


def test_seed_demo_data_and_orm_demo():
    assert "12 книг" in run("seed_demo_data")
    assert Book.objects.count() == 12 and Category.objects.count() == 3
    run("seed_demo_data")  # повторний запуск перезаписує, а не дублює
    assert Book.objects.count() == 12
    output = run("demo_orm_queries")
    assert "Q-об'єкти" in output and "мартін" in output.lower() and "annotate()" in output
    assert "Роберт Мартін" in output  # кириличний icontains працює


@pytest.mark.skipif(connection.vendor == "postgresql", reason="на PostgreSQL аліас sqlite_legacy існує")
def test_migrate_sqlite_to_postgres_refuses_without_postgres():
    with pytest.raises(CommandError, match="sqlite_legacy"):
        call_command("migrate_sqlite_to_postgres")


# ------------------------------------------------------ SQLite unicode LIKE

@pytest.mark.parametrize("pattern, value, expected", [
    ("%мартін%", "Джордж Мартін", True), ("%МАРТІН%", "джордж мартін", True), ("%дюна%", "Кобзар", False),
    ("Дюна", "дюна", True), ("Д_на", "Дюна", True), ("%", "", True), ("%.%", "abc", False), ("%12%", 12345, True),
])
def test_unicode_like(pattern, value, expected):
    assert _unicode_like(pattern, value) is expected


def test_unicode_like_none():
    assert _unicode_like(None, "x") is None and _unicode_like("%", None) is None


@pytest.mark.skipif(connection.vendor != "sqlite", reason="лише SQLite")
def test_icontains_cyrillic_via_orm():
    BookFactory(author="Тарас Шевченко")
    assert Book.objects.filter(author__icontains="шевченко").count() == 1


# ---------------------------------------------------------------- middleware

def get_response(request):
    return HttpResponse("ok", status=201)


def test_middleware_logs_request(caplog):
    request = RequestFactory().get("/books/?q=x")
    request.user = User(username="alisa")
    with caplog.at_level("INFO", logger="config.middleware"):
        response = RequestLoggingMiddleware(get_response)(request)
    assert response.status_code == 201
    assert "GET /books/?q=x -> 201" in caplog.text and "user=alisa" in caplog.text


def test_middleware_anonymous_and_health_skipped(caplog):
    from django.contrib.auth.models import AnonymousUser
    mw = RequestLoggingMiddleware(get_response)
    with caplog.at_level("INFO", logger="config.middleware"):
        req = RequestFactory().get("/x/")
        req.user = AnonymousUser()
        mw(req)
        health = RequestFactory().get("/health/")
        health.user = AnonymousUser()
        mw(health)
    assert "user=anonymous" in caplog.text and "/health/" not in caplog.text


@pytest.mark.skipif(connection.vendor != "postgresql", reason="потрібен PostgreSQL")
def test_migrate_command_requires_legacy_file(tmp_path):
    from django.conf import settings
    with mock.patch.dict(settings.DATABASES["sqlite_legacy"], {"NAME": str(tmp_path / "missing.sqlite3")}):
        with pytest.raises(CommandError, match="не знайдено"):
            call_command("migrate_sqlite_to_postgres")
