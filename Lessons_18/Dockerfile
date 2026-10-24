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
COPY requirements.txt .
RUN pip install -r requirements.txt

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
CMD ["sh", "-c", "exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers ${GUNICORN_WORKERS:-3} --access-logfile -"]
