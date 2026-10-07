"""Views застосунку accounts: реєстрація, логін, логаут."""

from __future__ import annotations

import logging

from django.contrib.auth import login
from django.contrib.auth.views import LoginView as BaseLoginView
from django.contrib.auth.views import LogoutView as BaseLogoutView
from django.urls import reverse_lazy
from django.views.generic import CreateView

from .forms import LoginForm, RegisterForm

logger = logging.getLogger(__name__)


class RegisterView(CreateView):
    """Реєстрація нового користувача з автоматичним логіном після успіху."""

    form_class = RegisterForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("catalog:book-list")

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        logger.info("Новий користувач зареєструвався: %s", self.object.username)
        return response


class LoginView(BaseLoginView):
    """Логін через кастомну Bootstrap-форму та власний шаблон."""

    authentication_form = LoginForm
    template_name = "accounts/login.html"

    def form_valid(self, form):
        logger.info("Користувач увійшов: %s", form.get_user().username)
        return super().form_valid(form)


class LogoutView(BaseLogoutView):
    """Логаут. Django (з 5.0) приймає лише POST, тому в navbar — форма з кнопкою."""

    next_page = reverse_lazy("catalog:book-list")
