"""
Демонстрація роботи примітивної системи управління магазином.

Скрипт:
    1. Створює магазин.
    2. Зчитує початковий стан товарів і клієнтів з txt-файлів.
    3. Демонструє зміну ціни/кількості товару.
    4. Створює замовлення для клієнта та виводить підсумок.
"""

from __future__ import annotations

from pathlib import Path

from shop_system import Shop

DATA_DIR = Path(__file__).parent / "data"


def main() -> None:
    """Точка входу демонстраційного скрипта."""
    shop = Shop()

    # 1. Зчитування початкового стану з файлів
    shop.load_products(DATA_DIR / "products.txt")
    shop.load_customers(DATA_DIR / "customers.txt")

    print("=== Товари на складі ===")
    for product in shop.products.values():
        print(f"  {product}")

    print("\n=== Клієнти магазину ===")
    for customer in shop.customers.values():
        print(f"  {customer}")

    # 2. Демонстрація зміни ціни та кількості товару
    print("\n=== Зміна ціни та кількості товару ===")
    teddy_bear = shop.find_product("Плюшевий ведмедик")
    print(f"До зміни: {teddy_bear}")
    teddy_bear.change_price(399.00)
    teddy_bear.change_quantity(20)  # надходження нової партії
    print(f"Після зміни: {teddy_bear}")

    # 3. Створення замовлення для клієнта
    print("\n=== Створення замовлення ===")
    order = shop.create_order(
        customer_email="olena.kovalchuk@example.com",
        items=[
            ("Плюшевий ведмедик", 2),
            ("Пазл \"Природа\" 1000 елементів", 1),
        ],
    )
    print(f"Створено замовлення: {order}")
    for item in order.items:
        print(f"  - {item.product.name} x{item.quantity} = {item.subtotal:.2f}")
    print(f"Загальна сума замовлення: {order.calculate_total():.2f}")

    customer = shop.find_customer("olena.kovalchuk@example.com")
    print(f"\nУ клієнта {customer.name} тепер {len(customer.orders)} замовлення(-нь).")

    print(f"\nЗалишок товару '{teddy_bear.name}' на складі після замовлення: "
          f"{teddy_bear.quantity}")


if __name__ == "__main__":
    main()