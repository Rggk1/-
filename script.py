"""
Практикум: Динамические линейные преобразования.
Математический анализ, РПО-25/2.

Файл содержит решения трёх задач (NumPy не используется):
  1. Динамическая телепортация персонажа (сложение векторов).
  2. Поворот и масштабирование в 2D (умножение матриц циклами).
  3. Параметризуемый полносвязный слой нейросети z = W x + b.

Все данные вводятся пользователем с клавиатуры.
"""

import math


# ---------------------------------------------------------------------------
# Общие функции ввода с проверкой корректности
# ---------------------------------------------------------------------------

def read_float(prompt):
    """Читает одно вещественное число. Повторяет запрос при ошибке.
    Запятая как десятичный разделитель тоже допускается ("1,5" -> 1.5)."""
    while True:
        text = input(prompt).strip().replace(",", ".")
        try:
            value = float(text)
        except ValueError:
            print("  Ошибка: нужно ввести число.")
            continue
        # float("nan") и float("inf") парсятся без ошибки, но бесполезны
        if math.isnan(value) or math.isinf(value):
            print("  Ошибка: число должно быть конечным.")
            continue
        return value


def read_int_in_range(prompt, low, high=None):
    """Читает целое число не меньше low (и не больше high, если задано)."""
    while True:
        text = input(prompt).strip()
        try:
            value = int(text)
        except ValueError:
            print("  Ошибка: нужно ввести целое число.")
            continue
        if value < low or (high is not None and value > high):
            limit = f"от {low} до {high}" if high is not None else f"не меньше {low}"
            print(f"  Ошибка: значение должно быть {limit}.")
            continue
        return value


def read_vector(name, size):
    """Читает вектор из size чисел по одному (пошагово)."""
    print(f"Ввод вектора {name} ({size} компонент):")
    return [read_float(f"  {name}[{i + 1}] = ") for i in range(size)]


def read_matrix(name, rows, cols):
    """Читает матрицу rows x cols построчно, элемент за элементом."""
    print(f"Ввод матрицы {name} ({rows}x{cols}):")
    matrix = []
    for i in range(rows):
        row = [read_float(f"  {name}[{i + 1}][{j + 1}] = ") for j in range(cols)]
        matrix.append(row)
    return matrix


def fmt_vec(v):
    """Красивый вывод вектора: (1.5, -2, 3)."""
    return "(" + ", ".join(f"{x:.6g}" for x in v) + ")"


def print_matrix(name, m):
    """Печатает матрицу построчно."""
    print(f"{name} =")
    for row in m:
        print("   [" + "  ".join(f"{x:10.6g}" for x in row) + " ]")


# ---------------------------------------------------------------------------
# Базовые операции линейной алгебры (всё через циклы)
# ---------------------------------------------------------------------------

def vec_add(a, b):
    """Покомпонентная сумма векторов одинаковой длины."""
    if len(a) != len(b):
        raise ValueError("Векторы должны быть одной размерности.")
    return [a[i] + b[i] for i in range(len(a))]


def vec_len(a):
    """Евклидова длина вектора: sqrt(x1^2 + x2^2 + ...)."""
    total = 0.0
    for x in a:
        total += x * x
    return math.sqrt(total)


def mat_mul(A, B):
    """Произведение матриц A (m x n) и B (n x k) тремя вложенными циклами:
    C[i][j] = sum_t A[i][t] * B[t][j]."""
    m, n = len(A), len(A[0])
    if len(B) != n:
        raise ValueError(
            f"Несогласованные размеры: A имеет {n} столбцов, а B - {len(B)} строк."
        )
    k = len(B[0])
    C = [[0.0] * k for _ in range(m)]
    for i in range(m):
        for j in range(k):
            for t in range(n):
                C[i][j] += A[i][t] * B[t][j]
    return C


def mat_vec(A, x):
    """Произведение матрицы A (m x n) на вектор-столбец x (n)."""
    n = len(A[0])
    if len(x) != n:
        raise ValueError(
            f"Несогласованные размеры: матрица имеет {n} столбцов, а вектор - {len(x)} компонент."
        )
    result = []
    for row in A:
        s = 0.0
        for j in range(n):
            s += row[j] * x[j]
        result.append(s)
    return result


# ---------------------------------------------------------------------------
# Задача 1. Динамическая телепортация персонажа
# ---------------------------------------------------------------------------

def task1():
    print("\n=== Задача 1. Телепортация персонажа ===")
    # Размерность карты выбирает пользователь (по заданию - плоская карта,
    # 3D добавлено для универсальности).
    dim = read_int_in_range("Размерность карты (2 или 3): ", 2, 3)

    A = read_vector("A", dim)  # начальная точка
    u = read_vector("u", dim)  # сдвиг первого портала
    v = read_vector("v", dim)  # сдвиг второго портала

    # Суммарный сдвиг r = u + v (перемещения складываются)
    r = vec_add(u, v)
    # Итоговая позиция B = A + r
    B = vec_add(A, r)

    # Прямое расстояние от A до B - длина результирующего вектора |r|.
    straight = vec_len(r)
    # Фактический путь: персонаж прошёл оба портала, т.е. |u| + |v|.
    route = vec_len(u) + vec_len(v)

    print(f"\nРезультирующий вектор r = u + v = {fmt_vec(r)}")
    print(f"Итоговая позиция B = {fmt_vec(B)}")
    print(f"Длина результирующего вектора |r| (расстояние A -> B): {straight:.6g}")
    print(f"Длина пройденного маршрута |u| + |v|: {route:.6g}")
    # Неравенство треугольника: |u+v| <= |u|+|v| - полезная самопроверка
    assert straight <= route + 1e-9


# ---------------------------------------------------------------------------
# Задача 2. Поворот и масштабирование в 2D
# ---------------------------------------------------------------------------

def task2():
    print("\n=== Задача 2. Поворот и масштабирование ===")
    x = read_vector("x", 2)
    R = read_matrix("R (поворот)", 2, 2)
    S = read_matrix("S (масштаб)", 2, 2)

    # Шаг 1: поворот x1 = R x. Шаг 2: масштабирование x2 = S x1
    x1 = mat_vec(R, x)
    x2 = mat_vec(S, x1)

    # Общая матрица: сначала действует R, потом S, поэтому T = S R (порядок важен!)
    T = mat_mul(S, R)
    Tx = mat_vec(T, x)

    print(f"\nx1 = R x = {fmt_vec(x1)}")
    print(f"x2 = S x1 = {fmt_vec(x2)}")
    print_matrix("T = S R", T)
    print(f"T x = {fmt_vec(Tx)}")

    # Сравнение вещественных чисел - только с допуском, а не через ==
    equal = all(math.isclose(Tx[i], x2[i], rel_tol=1e-9, abs_tol=1e-9) for i in range(2))
    print("Проверка T x == x2:", "выполнена" if equal else "НЕ выполнена")

    # Дополнительно: предупреждение, если R не похожа на матрицу поворота
    det_r = R[0][0] * R[1][1] - R[0][1] * R[1][0]
    if not math.isclose(det_r, 1.0, rel_tol=1e-6, abs_tol=1e-6):
        print(f"Замечание: det R = {det_r:.6g} != 1, значит R не является чистым поворотом "
              "(вычисления при этом корректны).")


# ---------------------------------------------------------------------------
# Задача 3. Параметризуемый нейронный слой
# ---------------------------------------------------------------------------

def dense_layer(x, W, b):
    """Полносвязный слой: z = W x + b.

    x - список длины N, W - список из M строк по N чисел, b - список длины M.
    При несогласованных размерах выбрасывает ValueError.
    """
    if not W or not W[0]:
        raise ValueError("Матрица весов W пуста.")
    M, N = len(W), len(W[0])
    # Все строки W должны иметь одинаковую длину
    if any(len(row) != N for row in W):
        raise ValueError("Строки матрицы W имеют разную длину.")
    if len(x) != N:
        raise ValueError(f"W имеет {N} столбцов, а длина x равна {len(x)} (ожидалось {N}).")
    if len(b) != M:
        raise ValueError(f"W имеет {M} строк, а длина b равна {len(b)} (ожидалось {M}).")

    z = mat_vec(W, x)
    # Добавляем смещение к каждому выходному нейрону
    return [z[i] + b[i] for i in range(M)]


def task3():
    print("\n=== Задача 3. Полносвязный слой ===")
    N = read_int_in_range("Размерность входа N (число признаков): ", 1)
    M = read_int_in_range("Число нейронов M (размерность выхода): ", 1)

    # Структуры создаются под введённые N и M
    x = read_vector("x", N)
    W = read_matrix("W", M, N)
    b = read_vector("b", M)

    try:
        z = dense_layer(x, W, b)
    except ValueError as err:
        print(f"Ошибка согласованности размеров: {err}")
        return

    print(f"\nz = W x + b = {fmt_vec(z)}")


# ---------------------------------------------------------------------------
# Главное меню
# ---------------------------------------------------------------------------

def main():
    tasks = {1: task1, 2: task2, 3: task3}
    while True:
        print("\n" + "=" * 40)
        print("1 - Телепортация персонажа")
        print("2 - Поворот и масштабирование")
        print("3 - Полносвязный слой")
        print("0 - Выход")
        choice = read_int_in_range("Выберите задачу: ", 0, 3)
        if choice == 0:
            print("Завершение работы.")
            break
        try:
            tasks[choice]()
        except ValueError as err:
            # Страховка: любая ошибка вычислений не должна ронять программу
            print(f"Ошибка: {err}")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nВвод прерван. Завершение работы.")