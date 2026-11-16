"""Unit-тести форм: RegisterForm, LoginForm, BookForm, CheckoutForm."""

import pytest
from django.utils import translation

from accounts.forms import LoginForm, RegisterForm
from catalog.forms import BookForm
from orders.forms import CheckoutForm

pytestmark = pytest.mark.django_db

REG = {"username": "newbie", "email": "newbie@example.com", "phone_number": "+380501234567",
       "password1": "Str0ng-Pass!42", "password2": "Str0ng-Pass!42"}


def test_register_form_creates_user():
    form = RegisterForm(REG)
    assert form.is_valid(), form.errors
    user = form.save()
    assert user.phone_number == "+380501234567" and user.check_password(REG["password1"])


@pytest.mark.parametrize("override, field", [
    ({"password2": "different-Pass!1"}, "password2"),
    ({"email": ""}, "email"),
    ({"email": "not-an-email"}, "email"),
    ({"password1": "123", "password2": "123"}, "password2"),
])
def test_register_form_invalid(override, field):
    form = RegisterForm({**REG, **override})
    assert not form.is_valid() and field in form.errors


def test_register_form_rejects_duplicate_username(user):
    assert "username" in RegisterForm({**REG, "username": user.username}).errors


def test_register_form_phone_is_optional():
    assert RegisterForm({**REG, "phone_number": ""}).is_valid()


def test_login_form(user, password):
    assert LoginForm(data={"username": user.username, "password": password}).is_valid()
    assert not LoginForm(data={"username": user.username, "password": "wrong"}).is_valid()


def test_login_form_has_bootstrap_classes():
    form = LoginForm()
    assert "form-control" in form.fields["username"].widget.attrs["class"]


def test_book_form_valid(category):
    form = BookForm({"title": "T", "author": "A", "price": "12.50", "description": "", "stock": 3, "category": category.pk})
    assert form.is_valid(), form.errors


@pytest.mark.parametrize("override, field", [
    ({"title": ""}, "title"), ({"stock": -1}, "stock"), ({"price": "abc"}, "price"), ({"category": 9999}, "category"),
])
def test_book_form_invalid(category, override, field):
    data = {"title": "T", "author": "A", "price": "12.50", "description": "", "stock": 3, "category": category.pk}
    assert field in BookForm({**data, **override}).errors


def test_book_form_labels_follow_language():
    with translation.override("en"):
        assert BookForm().fields["title"].label == "Title"
    with translation.override("uk"):
        assert BookForm().fields["title"].label == "Назва"


def test_checkout_form_valid_and_phone_optional():
    assert CheckoutForm({"full_name": "A B", "email": "a@b.com"}).is_valid()


@pytest.mark.parametrize("data", [{"full_name": "", "email": "a@b.com"}, {"full_name": "A", "email": "bad"}, {}])
def test_checkout_form_invalid(data):
    assert not CheckoutForm(data).is_valid()


def test_checkout_form_email_label_is_translated():
    with translation.override("en"):
        assert str(CheckoutForm().fields["email"].label) == "Email"
