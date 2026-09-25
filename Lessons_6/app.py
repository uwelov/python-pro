"""
book_list_app — навчальний Flask-додаток для обліку прочитаних книг.

Функціонал:
    * головна сторінка зі статистикою (скільки книг усього / прочитано);
    * сторінка зі списком усіх книг;
    * форма додавання нової книги (GET показує форму, POST обробляє дані);
    * перемикання статусу "прочитано / не прочитано" для конкретної книги.

Дані зберігаються просто в пам'яті процесу (список словників `books`),
без підключення бази даних — цього достатньо для навчальних цілей.
При перезапуску сервера всі додані книги скидаються до початкового набору.

Усі файли (app.py та .html-шаблони) лежать в одній директорії без
підпапок templates/ та static/ — тому Flask ініціалізовано з
template_folder="." , а CSS вбудовано прямо в base.html через <style>.
"""

from __future__ import annotations

from typing import TypedDict

from flask import Flask, render_template, request, redirect, url_for
from werkzeug.wrappers import Response

# Усі .html-файли лежать поруч з app.py (без окремої папки templates/),
# тому явно вказуємо Flask шукати шаблони в поточній директорії.
app = Flask(__name__, template_folder=".")


class Book(TypedDict):
    """Структура одного запису книги у списку `books`."""

    id: int
    title: str
    author: str
    year: int | None
    read: bool


books: list[Book] = [
    {"id": 1, "title": "1984", "author": "Джордж Оруелл", "year": 1949, "read": True},
    {"id": 2, "title": "Кобзар", "author": "Тарас Шевченко", "year": 1840, "read": True},
    {"id": 3, "title": "Дюна", "author": "Френк Герберт", "year": 1965, "read": False},
]


def get_next_id() -> int:
    """Обчислити наступний вільний id для нової книги.

    Returns:
        Найбільший наявний id, збільшений на 1. Якщо список книг порожній,
        повертає 1.
    """
    return max((b["id"] for b in books), default=0) + 1


@app.route("/")
def index() -> str:
    """Головна сторінка — коротка статистика по бібліотеці.

    Returns:
        Відрендерений HTML сторінки index.html із загальною кількістю
        книг та кількістю прочитаних.
    """
    total: int = len(books)
    read_count: int = sum(1 for b in books if b["read"])
    return render_template("index.html", total=total, read_count=read_count)


@app.route("/books")
def books_list() -> str:
    """Сторінка зі списком усіх книг у вигляді таблиці.

    Returns:
        Відрендерений HTML сторінки items.html з повним списком книг.
    """
    return render_template("items.html", books=books)


@app.route("/books/add", methods=["GET", "POST"])
def add_book() -> str | Response:
    """Показати форму додавання книги (GET) або обробити її надсилання (POST).

    При POST-запиті:
        * зчитує поля title, author, year з тіла форми;
        * якщо title і author заповнені — додає нову книгу до списку
          `books` і перенаправляє на сторінку списку книг;
        * якщо поля порожні — повторно показує форму з повідомленням
          про помилку та вже введеними значеннями (щоб їх не втратити).

    Returns:
        Або HTML форми (str), або HTTP-редирект (Response) на /books
        у разі успішного додавання.
    """
    if request.method == "POST":
        title: str = request.form.get("title", "").strip()
        author: str = request.form.get("author", "").strip()
        year_raw: str = request.form.get("year", "").strip()

        if title and author:
            new_book: Book = {
                "id": get_next_id(),
                "title": title,
                "author": author,
                "year": int(year_raw) if year_raw.isdigit() else None,
                "read": False,
            }
            books.append(new_book)
            return redirect(url_for("books_list"))

        error: str = "Будь ласка, заповніть назву та автора."
        return render_template(
            "add_book.html", error=error, title=title, author=author, year=year_raw
        )

    return render_template("add_book.html", error=None, title="", author="", year="")


@app.route("/books/<int:book_id>/toggle", methods=["POST"])
def toggle_read(book_id: int) -> Response:
    """Перемкнути статус "прочитано / не прочитано" для книги з заданим id.

    Args:
        book_id: Ідентифікатор книги (береться з URL, наприклад /books/2/toggle).

    Returns:
        HTTP-редирект на сторінку списку книг /books.
    """
    for b in books:
        if b["id"] == book_id:
            b["read"] = not b["read"]
            break
    return redirect(url_for("books_list"))


if __name__ == "__main__":
    app.run(debug=True)