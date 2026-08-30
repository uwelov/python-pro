"""
Примітивна система управління магазином.

Модуль містить класи:
    - Product - товар магазину;
    - Order - замовлення клієнта;
    - Customer - клієнт магазину;
    - Shop - сам магазин, що об'єднує товари й клієнтів та вміє зчитувати початковий стан з txt-файлів.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Union


class Product:
    """Товар магазину.

    Attributes:
        name (str): Назва товару.
        category (str): Категорія товару (наприклад, "м'яка іграшка", "конструктор").
        price (float): Ціна товару.
        quantity (int): Кількість товару на складі.
    """

    def __init__(self, name: str, category: str, price: float, quantity: int) -> None:
        """Ініціалізує товар.

        Args:
            name: Назва товару.
            category: Категорія товару.
            price: Ціна товару (має бути невід'ємною).
            quantity: Кількість на складі (має бути невід'ємною).

        Raises:
            ValueError: Якщо ціна або кількість від'ємні.
        """
        if price < 0:
            raise ValueError("Ціна не може бути від'ємною")
        if quantity < 0:
            raise ValueError("Кількість не може бути від'ємною")

        self.name: str = name
        self.category: str = category
        self.price: float = price
        self.quantity: int = quantity

    def change_price(self, new_price: float) -> None:
        """Змінює ціну товару.

        Args:
            new_price: Нова ціна товару.

        Raises:
            ValueError: Якщо нова ціна від'ємна.
        """
        if new_price < 0:
            raise ValueError("Ціна не може бути від'ємною")
        self.price = new_price

    def change_quantity(self, delta: int) -> None:
        """Змінює кількість товару на складі на вказану величину.

        Позитивне значення delta означає надходження товару,
        від'ємне - списання (наприклад, продаж).

        Args:
            delta: Величина зміни кількості.

        Raises:
            ValueError: Якщо результуюча кількість товару стає від'ємною.
        """
        new_quantity = self.quantity + delta
        if new_quantity < 0:
            raise ValueError(
                f"Недостатньо товару '{self.name}' на складі: "
                f"наявно {self.quantity}, потрібно {-delta}"
            )
        self.quantity = new_quantity

    def __repr__(self) -> str:
        return (
            f"Product(name={self.name!r}, category={self.category!r}, "
            f"price={self.price:.2f}, quantity={self.quantity})"
        )


class OrderItem:
    """Одна позиція в замовленні: товар та його кількість.

    Attributes:
        product (Product): Товар.
        quantity (int): Кількість одиниць товару в замовленні.
    """

    def __init__(self, product: Product, quantity: int) -> None:
        self.product: Product = product
        self.quantity: int = quantity

    @property
    def subtotal(self) -> float:
        """Повертає вартість цієї позиції (ціна * кількість)."""
        return self.product.price * self.quantity

    def __repr__(self) -> str:
        return f"OrderItem(product={self.product.name!r}, quantity={self.quantity})"


class Order:
    """Замовлення клієнта.

    Attributes:
        items (List[OrderItem]): Список позицій (товар + кількість) у замовленні.
        total (float): Загальна сума замовлення.
    """

    def __init__(self) -> None:
        self.items: List[OrderItem] = []
        self.total: float = 0.0

    def add_product(self, product: Product, quantity: int = 1) -> None:
        """Додає товар до замовлення та списує відповідну кількість зі складу.

        Args:
            product: Товар, який додається до замовлення.
            quantity: Кількість одиниць товару (за замовчуванням 1).

        Raises:
            ValueError: Якщо кількість не додатна, або товару
                недостатньо на складі.
        """
        if quantity <= 0:
            raise ValueError("Кількість товару в замовленні має бути додатною")

        product.change_quantity(-quantity)  # списуємо товар зі складу
        self.items.append(OrderItem(product=product, quantity=quantity))
        self.calculate_total()

    def calculate_total(self) -> float:
        """Обчислює та оновлює загальну суму замовлення.

        Returns:
            Загальна сума замовлення.
        """
        self.total = sum(item.subtotal for item in self.items)
        return self.total

    def __repr__(self) -> str:
        return f"Order(items={len(self.items)}, total={self.total:.2f})"


class Customer:
    """Клієнт магазину.

    Attributes:
        name (str): Ім'я клієнта.
        email (str): Електронна пошта клієнта.
        orders (List[Order]): Список замовлень клієнта.
    """

    def __init__(self, name: str, email: str) -> None:
        self.name: str = name
        self.email: str = email
        self.orders: List[Order] = []

    def add_order(self, order: Order) -> None:
        """Додає нове замовлення до списку замовлень клієнта.

        Args:
            order: Об'єкт замовлення, яке потрібно додати.
        """
        self.orders.append(order)

    def __repr__(self) -> str:
        return (
            f"Customer(name={self.name!r}, email={self.email!r}, "
            f"orders={len(self.orders)})"
        )


class Shop:
    """Магазин, що об'єднує товари та клієнтів.

    Вміє зчитувати початковий стан (товари та клієнтів) з txt-файлів.

    Attributes:
        products (Dict[str, Product]): Товари магазину, ключ - назва товару.
        customers (Dict[str, Customer]): Клієнти магазину, ключ - email.
    """

    def __init__(self) -> None:
        self.products: Dict[str, Product] = {}
        self.customers: Dict[str, Customer] = {}

    def load_products(self, filepath: Union[str, Path]) -> None:
        """Завантажує товари з txt-файлу.

        Очікуваний формат файлу (роздільник - крапка з комою),
        один товар на рядок:

            назва;категорія;ціна;кількість

        Рядки, що починаються з '#', та порожні рядки ігноруються.

        Args:
            filepath: Шлях до файлу з товарами.

        Raises:
            FileNotFoundError: Якщо файл не знайдено.
        """
        path = Path(filepath)
        with path.open("r", encoding="utf-8") as file:
            for line_number, raw_line in enumerate(file, start=1):
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue

                parts = [p.strip() for p in line.split(";")]
                if len(parts) != 4:
                    print(f"[products] Пропущено некоректний рядок {line_number}: {line!r}")
                    continue

                name, category, price_str, quantity_str = parts
                try:
                    product = Product(
                        name=name,
                        category=category,
                        price=float(price_str),
                        quantity=int(quantity_str),
                    )
                except ValueError as exc:
                    print(f"[products] Помилка в рядку {line_number}: {exc}")
                    continue

                self.products[product.name] = product

    def load_customers(self, filepath: Union[str, Path]) -> None:
        """Завантажує клієнтів з txt-файлу.

        Очікуваний формат файлу (роздільник - крапка з комою),
        один клієнт на рядок:

            ім'я;email

        Рядки, що починаються з '#', та порожні рядки ігноруються.

        Args:
            filepath: Шлях до файлу з клієнтами.

        Raises:
            FileNotFoundError: Якщо файл не знайдено.
        """
        path = Path(filepath)
        with path.open("r", encoding="utf-8") as file:
            for line_number, raw_line in enumerate(file, start=1):
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue

                parts = [p.strip() for p in line.split(";")]
                if len(parts) != 2:
                    print(f"[customers] Пропущено некоректний рядок {line_number}: {line!r}")
                    continue

                name, email = parts
                self.customers[email] = Customer(name=name, email=email)

    def find_product(self, name: str) -> Product:
        """Знаходить товар за назвою.

        Args:
            name: Назва товару.

        Returns:
            Знайдений об'єкт Product.

        Raises:
            KeyError: Якщо товар із такою назвою відсутній у магазині.
        """
        if name not in self.products:
            raise KeyError(f"Товар '{name}' не знайдено в магазині")
        return self.products[name]

    def find_customer(self, email: str) -> Customer:
        """Знаходить клієнта за email.

        Args:
            email: Електронна пошта клієнта.

        Returns:
            Знайдений об'єкт Customer.

        Raises:
            KeyError: Якщо клієнта з такою поштою не знайдено.
        """
        if email not in self.customers:
            raise KeyError(f"Клієнта з поштою '{email}' не знайдено")
        return self.customers[email]

    def create_order(self, customer_email: str, items: List[tuple[str, int]]) -> Order:
        """Створює замовлення для клієнта на основі списку (назва_товару, кількість).

        Args:
            customer_email: Email клієнта, для якого створюється замовлення.
            items: Список кортежів (назва_товару, кількість).

        Returns:
            Створене замовлення, вже додане до списку замовлень клієнта.

        Raises:
            KeyError: Якщо клієнта або якийсь із товарів не знайдено.
            ValueError: Якщо кількість товару недопустима або
                товару не вистачає на складі.
        """
        customer = self.find_customer(customer_email)
        order = Order()
        for product_name, quantity in items:
            product = self.find_product(product_name)
            order.add_product(product, quantity)
        customer.add_order(order)
        return order

    def __repr__(self) -> str:
        return f"Shop(products={len(self.products)}, customers={len(self.customers)})"