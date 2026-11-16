"""Тести async views (async def + async ORM). Дані створюються в синхронних фікстурах."""

import asyncio
import json

import pytest
from asgiref.sync import iscoroutinefunction
from django.urls import reverse

from catalog import async_views
from tests.factories import BookFactory, CategoryFactory

pytestmark = pytest.mark.django_db(transaction=True)  # async ORM працює в іншому потоці -> потрібні справжні коміти


@pytest.fixture
def catalog_data(db):
    fantasy, it = CategoryFactory(name="Фантастика", slug="fantasy"), CategoryFactory(name="IT", slug="it")
    BookFactory(title="Дюна", author="Герберт", price="450.00", stock=1, category=fantasy)
    BookFactory(title="Clean Code", author="Мартін", price="520.00", stock=0, category=it)
    BookFactory(title="Fluent Python", author="Ramalho", price="590.00", stock=9, category=it)


@pytest.mark.parametrize("view", [async_views.book_list_api, async_views.book_detail_api, async_views.category_list_api,
                                  async_views.stats_api, async_views.low_stock_api])
def test_views_are_coroutines(view):
    assert iscoroutinefunction(view)


async def test_book_list_search(async_client, catalog_data):
    data = (await async_client.get(reverse("catalog:api-book-list"), {"q": "МАРТІН"})).json()
    assert data["count"] == 1 and data["results"][0]["title"] == "Clean Code"
    assert data["results"][0]["category"]["slug"] == "it" and data["results"][0]["in_stock"] is False


async def test_book_list_category_filter_and_limit(async_client, catalog_data):
    url = reverse("catalog:api-book-list")
    assert (await async_client.get(url, {"category": "it"})).json()["count"] == 2
    limited = (await async_client.get(url, {"limit": 1})).json()
    assert limited["count"] == 3 and len(limited["results"]) == 1
    assert len((await async_client.get(url, {"limit": "abc"})).json()["results"]) == 3  # некоректний -> 10
    assert len((await async_client.get(url, {"limit": 0})).json()["results"]) == 1       # нижня межа 1


async def test_json_is_not_ascii_escaped(async_client, catalog_data):
    body = (await async_client.get(reverse("catalog:api-book-list"), {"q": "Дюна"})).content.decode()
    assert "Дюна" in body and "\\u" not in body


async def test_book_detail_found_and_missing(async_client, catalog_data):
    first = (await async_client.get(reverse("catalog:api-book-list"), {"q": "Дюна"})).json()["results"][0]
    ok = await async_client.get(reverse("catalog:api-book-detail", args=[first["id"]]))
    assert ok.status_code == 200 and ok.json()["price"] == "450.00"
    missing = await async_client.get(reverse("catalog:api-book-detail", args=[999999]), headers={"accept-language": "en"})
    assert missing.status_code == 404 and missing.json() == {"error": "Book not found."}


async def test_category_list_counts(async_client, catalog_data):
    data = (await async_client.get(reverse("catalog:api-category-list"))).json()
    assert {c["slug"]: c["book_count"] for c in data} == {"fantasy": 1, "it": 2}


async def test_stats(async_client, catalog_data):
    data = (await async_client.get(reverse("catalog:api-stats"))).json()
    assert (data["books"], data["books_in_stock"], data["books_out_of_stock"], data["categories"]) == (3, 2, 1, 2)
    assert data["units_in_stock"] == 10 and data["price"] == {"avg": "520.00", "min": "450.00", "max": "590.00"}


async def test_stats_on_empty_database(async_client, db):
    data = (await async_client.get(reverse("catalog:api-stats"))).json()
    assert data["books"] == 0 and data["price"]["avg"] is None and data["units_in_stock"] == 0


async def test_low_stock_requires_auth_and_permission(async_client, catalog_data, customer, librarian):
    url = reverse("catalog:api-low-stock")
    assert (await async_client.get(url)).status_code == 401
    await async_client.aforce_login(customer)
    assert (await async_client.get(url)).status_code == 403
    await async_client.aforce_login(librarian)
    data = (await async_client.get(url)).json()
    assert [b["title"] for b in data["results"]] == ["Clean Code", "Дюна"]  # сортування за залишком


async def test_only_get_is_allowed(async_client, catalog_data):
    assert (await async_client.post(reverse("catalog:api-stats"))).status_code == 405


async def test_concurrent_requests(async_client, catalog_data):
    responses = await asyncio.gather(*(async_client.get(reverse("catalog:api-stats")) for _ in range(5)))
    assert [r.status_code for r in responses] == [200] * 5
    assert len({json.dumps(r.json(), sort_keys=True) for r in responses}) == 1


async def test_async_middleware_logs_user(async_client, catalog_data, librarian, caplog):
    await async_client.aforce_login(librarian)
    with caplog.at_level("INFO", logger="config.middleware"):
        await async_client.get(reverse("catalog:api-stats"))
    assert any("/api/stats/" in r.getMessage() and f"user={librarian.username}" in r.getMessage() for r in caplog.records)
