"""Власний middleware проєкту."""

from __future__ import annotations

import logging
import time
from typing import Callable

from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware:
    """Логує кожен HTTP-запит: метод, шлях, користувача, статус і тривалість.

    Middleware підключається один раз при старті сервера (Django створює
    один екземпляр і викликає його для кожного запиту), тому важка
    ініціалізація виконується у __init__, а сама обробка запиту — у
    __call__, як того вимагає інтерфейс Django middleware.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        start_time = time.monotonic()

        response = self.get_response(request)

        duration_ms = (time.monotonic() - start_time) * 1000
        user = request.user if hasattr(request, "user") else None
        username = (
            user.get_username() if user and user.is_authenticated else "anonymous"
        )

        logger.info(
            "%s %s -> %s (%.1f ms) [user=%s]",
            request.method,
            request.get_full_path(),
            response.status_code,
            duration_ms,
            username,
        )

        return response
