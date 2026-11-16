# legacy/

Покладіть сюди свій старий файл **`db.sqlite3`**, якщо хочете перенести дані
в PostgreSQL:

```
legacy/db.sqlite3
```

Потім: `docker compose exec web python manage.py migrate_sqlite_to_postgres`

Папка монтується в контейнер лише для читання (`/app/legacy`).
