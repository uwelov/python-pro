#!/bin/sh
# Точка входу контейнера web: готує базу та статику, потім запускає основну команду.
set -e

# 1. Чекаємо на PostgreSQL. У docker-compose це вже гарантує healthcheck
#    (depends_on: condition: service_healthy), але перевірка робить контейнер
#    стійким і при запуску без compose.
if [ "$DB_ENGINE" = "postgres" ]; then
    echo "[entrypoint] Чекаю на PostgreSQL (${POSTGRES_HOST}:${POSTGRES_PORT:-5432})..."
    python - <<'PY'
import os, sys, time
import psycopg

params = dict(
    dbname=os.environ["POSTGRES_DB"],
    user=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
    host=os.environ.get("POSTGRES_HOST", "localhost"),
    port=os.environ.get("POSTGRES_PORT", "5432"),
    connect_timeout=3,
)
for attempt in range(1, 31):
    try:
        psycopg.connect(**params).close()
        print(f"[entrypoint] PostgreSQL доступний (спроба {attempt})")
        sys.exit(0)
    except psycopg.OperationalError as exc:
        print(f"[entrypoint] ще не готовий ({attempt}/30): {exc}".splitlines()[0])
        time.sleep(2)
print("[entrypoint] PostgreSQL недоступний — виходжу", file=sys.stderr)
sys.exit(1)
PY
fi

# 2. Міграції.
echo "[entrypoint] Застосовую міграції..."
python manage.py migrate --noinput

# 3. Статика -> /app/staticfiles (volume), звідки її віддає WhiteNoise.
echo "[entrypoint] Збираю статичні файли..."
python manage.py collectstatic --noinput --verbosity 0

# 4. Групи та права (ідемпотентно).
if [ "${SETUP_GROUPS:-0}" = "1" ]; then
    echo "[entrypoint] Налаштовую групи користувачів..."
    python manage.py setup_groups
fi

# 5. Суперкористувач (лише якщо змінні задані; якщо вже існує — пропускаємо).
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    echo "[entrypoint] Створюю суперкористувача '$DJANGO_SUPERUSER_USERNAME' (якщо ще немає)..."
    python manage.py createsuperuser --noinput 2>/dev/null \
        || echo "[entrypoint] суперкористувач уже існує — пропускаю"
fi

echo "[entrypoint] Готово, запускаю: $*"
exec "$@"
