"""Health-check endpoint для Docker/оркестратора: перевіряє БД та кеш (Redis)."""

from __future__ import annotations

from django.core.cache import cache
from django.db import connection
from django.http import HttpRequest, JsonResponse


def health(request: HttpRequest) -> JsonResponse:
    """Повертає 200, якщо працюють і БД, і кеш; інакше 503 з описом проблеми."""
    checks: dict[str, str] = {}

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 — потрібно перехопити будь-яку помилку з'єднання
        checks["database"] = f"error: {exc.__class__.__name__}"

    try:
        cache.set("health-check", "ok", timeout=10)
        checks["cache"] = "ok" if cache.get("health-check") == "ok" else "error: no value"
    except Exception as exc:  # noqa: BLE001
        checks["cache"] = f"error: {exc.__class__.__name__}"

    healthy = all(value == "ok" for value in checks.values())
    return JsonResponse(
        {"status": "ok" if healthy else "unhealthy", **checks},
        status=200 if healthy else 503,
    )
