"""Адмінка для кастомної моделі User."""

from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Розширюємо стандартну UserAdmin полем phone_number."""

    fieldsets = BaseUserAdmin.fieldsets + (
        ("Додаткова інформація", {"fields": ("phone_number",)}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Додаткова інформація", {"fields": ("phone_number",)}),
    )
    list_display = (
        "username",
        "email",
        "phone_number",
        "is_staff",
        "is_active",
    )
    search_fields = ("username", "email", "phone_number")
