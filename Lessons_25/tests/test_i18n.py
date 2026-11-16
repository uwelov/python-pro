"""Тести інтернаціоналізації (uk + en): каталоги .po/.mo, переклади, множина, перемикання мови."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import polib
import pytest
from django.conf import settings
from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext, ngettext

from tests.factories import BookFactory, OrderFactory

LOCALE = Path(settings.BASE_DIR) / "locale"
PLACEHOLDER = re.compile(r"%\(\w+\)[sd]|%[sd]")


@pytest.mark.parametrize("lang", ["uk", "en"])
def test_catalog_is_complete(lang):
    po = polib.pofile(str(LOCALE / lang / "LC_MESSAGES" / "django.po"))
    assert len(po) > 100
    assert [e.msgid for e in po.untranslated_entries()] == []
    assert [e.msgid for e in po.fuzzy_entries()] == []
    assert po.obsolete_entries() == []


@pytest.mark.parametrize("lang", ["uk", "en"])
def test_placeholders_match_between_msgid_and_msgstr(lang):
    for entry in polib.pofile(str(LOCALE / lang / "LC_MESSAGES" / "django.po")):
        if entry.msgid_plural:
            continue
        assert sorted(PLACEHOLDER.findall(entry.msgid)) == sorted(PLACEHOLDER.findall(entry.msgstr)), entry.msgid


@pytest.mark.parametrize("lang", ["uk", "en"])
def test_mo_is_compiled_and_current(lang):
    base = LOCALE / lang / "LC_MESSAGES"
    assert (base / "django.mo").exists()
    assert (base / "django.mo").stat().st_mtime >= (base / "django.po").stat().st_mtime - 1, "виконайте compilemessages"
    mo = polib.mofile(str(base / "django.mo"))
    assert len(mo) == len(polib.pofile(str(base / "django.po")))


def test_settings():
    assert settings.LANGUAGE_CODE == "uk" and [c for c, _ in settings.LANGUAGES] == ["uk", "en"]
    assert "django.middleware.locale.LocaleMiddleware" in settings.MIDDLEWARE


@pytest.mark.parametrize("n, word", [(1, "примірник"), (2, "примірники"), (4, "примірники"), (5, "примірників"),
                                     (11, "примірників"), (21, "примірник"), (22, "примірники"), (25, "примірників")])
def test_ukrainian_plural_forms(n, word):
    with translation.override("uk"):
        text = ngettext("«%(title)s»: у кошику %(count)d примірник", "«%(title)s»: у кошику %(count)d примірників", n)
    assert text.endswith(word)


@pytest.mark.parametrize("n, text", [(1, "1 copy in the cart"), (3, "3 copies in the cart")])
def test_english_plural_forms(n, text):
    with translation.override("en"):
        assert ngettext("«%(title)s»: у кошику %(count)d примірник", "«%(title)s»: у кошику %(count)d примірників", n) % {"title": "x", "count": n} == f"“x”: {text}"


def test_gettext_both_directions():
    with translation.override("en"):
        assert gettext("Кошик очищено.") == "The cart has been cleared."
    with translation.override("uk"):
        assert gettext("Кошик очищено.") == "Кошик очищено."


def test_unknown_msgid_falls_back_to_source():
    with translation.override("en"):
        assert gettext("Такого рядка немає в каталозі") == "Такого рядка немає в каталозі"


@pytest.mark.django_db
class TestPages:
    def test_default_language_is_ukrainian(self, client):
        page = client.get(reverse("catalog:book-list")).content.decode()
        assert "Каталог книг" in page and '<html lang="uk">' in page

    def test_switch_language_sets_cookie_and_persists(self, client):
        r = client.post(reverse("set_language"), {"language": "en", "next": "/categories/"})
        assert r.status_code == 302 and r["Location"] == "/categories/" and r.cookies[settings.LANGUAGE_COOKIE_NAME].value == "en"
        assert "Book categories" in client.get("/categories/").content.decode()

    def test_unsupported_language_is_ignored(self, client):
        client.post(reverse("set_language"), {"language": "de", "next": "/"})
        assert "Каталог книг" in client.get(reverse("catalog:book-list")).content.decode()

    def test_accept_language_negotiation(self, client):
        assert "Book catalog" in client.get("/", headers={"accept-language": "en-US,en;q=0.9"}).content.decode()
        assert "Каталог книг" in client.get("/", headers={"accept-language": "de"}).content.decode()

    def test_switcher_is_rendered(self, client):
        page = client.get("/").content.decode()
        assert 'name="language" value="en"' in page and 'name="language" value="uk"' in page

    def test_auth_pages_translated(self, client):
        assert "Log in" in client.get(reverse("accounts:login"), headers={"accept-language": "en"}).content.decode()
        assert "Вхід" in client.get(reverse("accounts:login")).content.decode()

    def test_numbers_are_localized(self, client):
        book = BookFactory(price="1234.50")
        assert "1234,50" in client.get(book.get_absolute_url()).content.decode()
        assert "1234.50" in client.get(book.get_absolute_url(), headers={"accept-language": "en"}).content.decode()

    def test_order_page_status_is_translated(self, login, user, book):
        order = OrderFactory(user=user, items=[(book, 1)])
        client = login(user)
        assert "Awaiting payment" in client.get(order.get_absolute_url(), headers={"accept-language": "en"}).content.decode()
        assert "Очікує оплати" in client.get(order.get_absolute_url()).content.decode()

    def test_admin_is_translated(self, login, superuser):
        page = login(superuser).get(reverse("admin:catalog_book_changelist"), headers={"accept-language": "en"}).content.decode()
        assert "Books" in page and "stock availability" in page


@pytest.mark.skipif(not shutil.which("xgettext"), reason="GNU gettext не встановлено")
def test_po_is_up_to_date_with_source(tmp_path):
    """Каталог не відстає від коду: свіжий makemessages у копії проєкту дає ті самі msgid."""
    work = tmp_path / "project"
    shutil.copytree(settings.BASE_DIR, work, ignore=shutil.ignore_patterns(
        ".git", "__pycache__", "staticfiles", ".venv", "venv", "*.sqlite3", "logs", ".coverage*", "htmlcov", ".pytest_cache"))
    subprocess.run(
        [sys.executable, "manage.py", "makemessages", "-l", "en", "--no-location",
         "--ignore=tests/*", "--ignore=*/tests.py", "--ignore=staticfiles/*"],
        cwd=work, env={**os.environ, "DB_ENGINE": "sqlite"}, check=True, capture_output=True,
    )
    path = "locale/en/LC_MESSAGES/django.po"
    fresh = {e.msgid for e in polib.pofile(str(work / path)) if not e.obsolete}
    committed = {e.msgid for e in polib.pofile(str(Path(settings.BASE_DIR) / path))}
    assert fresh == committed, "виконайте makemessages + locale/fill_translations.py + compilemessages"
