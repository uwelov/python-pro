"""URLconf застосунку orders (кошик, замовлення, вебхук Stripe). namespace='orders'."""

from __future__ import annotations

from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    # Кошик
    path("cart/", views.CartDetailView.as_view(), name="cart-detail"),
    path("cart/add/<int:book_id>/", views.cart_add, name="cart-add"),
    path("cart/remove/<int:book_id>/", views.cart_remove, name="cart-remove"),
    path("cart/clear/", views.cart_clear, name="cart-clear"),
    # Замовлення
    path("orders/", views.OrderListView.as_view(), name="order-list"),
    path("orders/checkout/", views.CheckoutView.as_view(), name="checkout"),
    path("orders/<int:pk>/", views.OrderDetailView.as_view(), name="order-detail"),
    path("orders/<int:pk>/pay/", views.order_pay, name="order-pay"),
    path("orders/<int:pk>/cancel/", views.order_cancel, name="order-cancel"),
    path("orders/<int:pk>/success/", views.order_success, name="order-success"),
    # Stripe
    path("stripe/webhook/", views.stripe_webhook, name="stripe-webhook"),
]
