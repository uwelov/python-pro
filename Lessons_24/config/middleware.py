"""Власний middleware проєкту."""

from __future__ import annotations

import logging
import time
from asyncio import iscoroutinefunction

from asgiref.sync import markcoroutinefunction
from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)

# Службові шляхи, які не логуємо (healthcheck Docker б'є кожні кілька секунд).
SKIP_PATHS = frozenset({"/health/"})


class RequestLoggingMiddleware:
    """Логує кожен HTTP-запит: метод, шлях, користувача, статус і тривалість.

    Middleware «двоїстий» (sync + async): під WSGI працює синхронно, під ASGI — як
    корутина, тож не змушує Django загортати весь ланцюжок у потоки. В async-режимі
    користувача беремо через `await request.auser()`, бо `request.user.is_authenticated`
    може піти в БД синхронно, що в event loop заборонено.
    """

    sync_capable = True
    async_capable = True

    def __init__(self, get_response) -> None:
        self.get_response = get_response
        if iscoroutinefunction(get_response):
            markcoroutinefunction(self)

    def __call__(self, request: HttpRequest):
        if iscoroutinefunction(self):
            return self.__acall__(request)
        start = time.monotonic()
        response = self.get_response(request)
        user = getattr(request, "user", None)
        username = user.get_username() if user is not None and user.is_authenticated else "anonymous"
        self._log(request, response, start, username)
        return response

    async def __acall__(self, request: HttpRequest) -> HttpResponse:
        start = time.monotonic()
        response = await self.get_response(request)
        username = "anonymous"
        if hasattr(request, "auser"):
            user = await request.auser()
            if user.is_authenticated:
                username = user.get_username()
        self._log(request, response, start, username)
        return response

    @staticmethod
    def _log(request: HttpRequest, response: HttpResponse, start: float, username: str) -> None:
        if request.path in SKIP_PATHS:
            return
        logger.info(
            "%s %s -> %s (%.1f ms) [user=%s]",
            request.method,
            request.get_full_path(),
            response.status_code,
            (time.monotonic() - start) * 1000,
            username,
        )
