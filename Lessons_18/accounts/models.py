"""Кастомна модель користувача.

Створюється на самому початку проєкту (до першої міграції auth-залежних
застосунків), бо Django не дозволяє підмінити AUTH_USER_MODEL після того,
як міграції з FK на стандартний User вже застосовані до бази.
"""

from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Користувач книгарні: стандартні поля Django + телефон.

    Успадковуємо AbstractUser (а не AbstractBaseUser), щоб залишити
    готову систему username/password/is_staff/is_superuser та не
    переписувати менеджер користувачів з нуля — для навчального проєкту
    цього достатньо, а дрібна кастомізація (телефон) демонструє сам
    механізм підміни моделі користувача.
    """

    phone_number = models.CharField(
        "Телефон",
        max_length=32,
        blank=True,
        help_text="Необов'язково. Формат: +380XXXXXXXXX",
    )

    class Meta:
        verbose_name = "Користувач"
        verbose_name_plural = "Користувачі"

    def __str__(self) -> str:
        return self.get_username()
