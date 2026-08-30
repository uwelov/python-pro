"""
Модуль з базовими функціями для практики Python:
робота з рядками, числами, списками, словниками, множинами,
умовними виразами, циклами та лямбда-функціями.
"""


# 1. Строки

def string_length(s: str) -> int:
    """
    Повертає довжину переданого рядка.

    Args:
        s (str): Вхідний рядок.

    Returns:
        int: Кількість символів у рядку.
    """
    return len(s)


def concat_strings(s1: str, s2: str) -> str:
    """
    Об'єднує два рядки в один.

    Args:
        s1 (str): Перший рядок.
        s2 (str): Другий рядок.

    Returns:
        str: Результат об'єднання s1 та s2.
    """
    return s1 + s2


# 2. Числа

def square(n: float) -> float:
    """
    Обчислює квадрат числа.

    Args:
        n (float): Вхідне число.

    Returns:
        float: Квадрат числа n.
    """
    return n ** 2


def add(a: float, b: float) -> float:
    """
    Повертає суму двох чисел.

    Args:
        a (float): Перше число.
        b (float): Друге число.

    Returns:
        float: Сума a + b.
    """
    return a + b


def divide_with_remainder(a: int, b: int) -> tuple[int, int]:
    """
    Виконує цілочисельне ділення та повертає цілу частину і залишок.

    Args:
        a (int): Ділене.
        b (int): Дільник (не має дорівнювати 0).

    Returns:
        tuple[int, int]: Кортеж (ціла частина, залишок).

    Raises:
        ZeroDivisionError: Якщо b дорівнює 0.
    """
    return a // b, a % b


# 3. Списки

def average(numbers: list[float]) -> float:
    """
    Обчислює середнє арифметичне значення списку чисел.

    Args:
        numbers (list[float]): Список чисел.

    Returns:
        float: Середнє значення. Якщо список порожній — повертає 0.
    """
    return sum(numbers) / len(numbers) if numbers else 0


def common_elements(list1: list, list2: list) -> list:
    """
    Знаходить спільні елементи двох списків.

    Args:
        list1 (list): Перший список.
        list2 (list): Другий список.

    Returns:
        list: Список елементів, присутніх в обох списках.
    """
    return list(set(list1) & set(list2))


# 4. Словари

def print_keys(d: dict) -> None:
    """
    Виводить у консоль усі ключі переданого словника.

    Args:
        d (dict): Вхідний словник.

    Returns:
        None
    """
    for key in d.keys():
        print(key)


def merge_dicts(d1: dict, d2: dict) -> dict:
    """
    Об'єднує два словники в новий.

    Якщо ключі повторюються, значення з d2 перезаписують значення з d1.

    Args:
        d1 (dict): Перший словник.
        d2 (dict): Другий словник (пріоритетний при збігу ключів).

    Returns:
        dict: Новий об'єднаний словник.
    """
    return {**d1, **d2}


# 5. Множества

def union_sets(s1: set, s2: set) -> set:
    """
    Обчислює об'єднання двох множин.

    Args:
        s1 (set): Перша множина.
        s2 (set): Друга множина.

    Returns:
        set: Множина, що містить усі унікальні елементи s1 та s2.
    """
    return s1 | s2


def is_subset(s1: set, s2: set) -> bool:
    """
    Перевіряє, чи є s1 підмножиною s2.

    Args:
        s1 (set): Множина, яку перевіряємо.
        s2 (set): Множина, відносно якої перевіряємо.

    Returns:
        bool: True, якщо всі елементи s1 містяться в s2, інакше False.
    """
    return s1.issubset(s2)


# 6. Условия и циклы

def check_even_odd(n: int) -> None:
    """
    Виводить у консоль, чи є число парним чи непарним.

    Args:
        n (int): Вхідне ціле число.

    Returns:
        None
    """
    print("Парне" if n % 2 == 0 else "Непарне")


def filter_even(numbers: list[int]) -> list[int]:
    """
    Відбирає лише парні числа зі списку.

    Args:
        numbers (list[int]): Список цілих чисел.

    Returns:
        list[int]: Новий список, що містить тільки парні числа.
    """
    return [n for n in numbers if n % 2 == 0]


# 7. Лямбда-функция

even_odd = lambda n: "парне" if n % 2 == 0 else "не парне"
"""
Callable[[int], str]: Лямбда-функція для визначення парності числа.

Args:
    n (int): Вхідне число.

Returns:
    str: "парне" або "не парне".
"""


if __name__ == "__main__":
    # 1. Строки
    s = input("Введите строку: ")
    print("Длина строки:", string_length(s))

    s1 = input("Введите первую строку: ")
    s2 = input("Введите вторую строку: ")
    print("Объединённая строка:", concat_strings(s1, s2))

    # 2. Числа
    num = float(input("Введите число для возведения в квадрат: "))
    print("Квадрат:", square(num))

    a = float(input("Введите первое число: "))
    b = float(input("Введите второе число: "))
    print("Сумма:", add(a, b))

    a_int = int(input("Введите первое целое число (для деления): "))
    b_int = int(input("Введите второе целое число (делитель): "))
    quotient, remainder = divide_with_remainder(a_int, b_int)
    print(f"Целая часть: {quotient}, остаток: {remainder}")

    # 3. Списки
    nums_input = input("Введите числа через пробел (для среднего значения): ")
    nums_list = [float(x) for x in nums_input.split()]
    print("Среднее значение:", average(nums_list))

    list1_input = input("Введите первый список чисел через пробел: ")
    list2_input = input("Введите второй список чисел через пробел: ")
    list1 = [int(x) for x in list1_input.split()]
    list2 = [int(x) for x in list2_input.split()]
    print("Общие элементы:", common_elements(list1, list2))

    # 4. Словари
    print("Ключи словаря {'a': 1, 'b': 2}:")
    print_keys({'a': 1, 'b': 2})

    d1 = {'a': 1, 'b': 2}
    d2 = {'b': 3, 'c': 4}
    print("Объединённый словарь:", merge_dicts(d1, d2))

    # 5. Множества
    set1_input = input("Введите элементы первого множества через пробел: ")
    set2_input = input("Введите элементы второго множества через пробел: ")
    set1 = set(set1_input.split())
    set2 = set(set2_input.split())
    print("Объединение множеств:", union_sets(set1, set2))
    print("Является ли первое подмножеством второго:", is_subset(set1, set2))

    # 6. Условия и циклы
    n = int(input("Введите число (чётное/нечётное): "))
    check_even_odd(n)

    nums_input2 = input("Введите числа через пробел (для фильтрации чётных): ")
    nums_list2 = [int(x) for x in nums_input2.split()]
    print("Чётные числа:", filter_even(nums_list2))

    # 7. Лямбда-функция
    n_lambda = int(input("Введите число (лямбда, чётное/нечётное): "))
    print(even_odd(n_lambda))
