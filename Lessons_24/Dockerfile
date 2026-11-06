FROM python:3.12-slim

# PYTHONUNBUFFERED — логи одразу в `docker logs`; PYTHONUTF8 — стабільне
# кодування файлів (кирилиця в dumpdata/loaddata, логах).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Залежності окремим шаром: перезбірка йде швидко, поки requirements.txt не змінювався.
# INSTALL_DEV=true додає pytest та інше з requirements-dev.txt (для запуску тестів у контейнері).
ARG INSTALL_DEV=false
COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements.txt \
    && if [ "$INSTALL_DEV" = "true" ]; then pip install -r requirements-dev.txt; fi

COPY . .

# Окремий непривілейований користувач. Папки staticfiles/logs створюємо
# заздалегідь, щоб іменовані volume успадкували правильного власника.
# sed прибирає Windows-перенесення рядків (CRLF), які ламають shell-скрипт.
RUN useradd --create-home --uid 1000 app \
    && sed -i 's/\r$//' /app/docker-entrypoint.sh \
    && chmod +x /app/docker-entrypoint.sh \
    && mkdir -p /app/staticfiles /app/logs \
    && chown -R app:app /app

USER app

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
# ASGI-сервер: async views виконуються повноцінно (під WSGI вони йшли б через потік-обгортку).
# Кількість процесів задає WEB_CONCURRENCY (uvicorn читає її сам). Lifespan Django не підтримує.
CMD ["uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--lifespan", "off", "--proxy-headers"]
