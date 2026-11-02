"""Расчёт количества заказов и выручки по артикулу и дню."""

import argparse
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path


COLUMNS = ["order_id", "order_date", "sku", "quantity", "price", "status"]


def order_revenue(row):
    """Проверить заказ и вернуть выручку. Для отмены количество не нужно."""
    for name in ("order_id", "order_date", "sku"):
        if not row[name]:
            raise ValueError(f"пустое поле {name}")

    try:
        parsed_date = date.fromisoformat(row["order_date"])
    except ValueError:
        raise ValueError("order_date должна быть датой в формате ГГГГ-ММ-ДД")
    if parsed_date.isoformat() != row["order_date"]:
        raise ValueError("order_date должна быть в формате ГГГГ-ММ-ДД")

    if row["status"] == "cancelled":
        return Decimal("0")
    if row["status"] != "delivered":
        raise ValueError(f"неизвестный статус: {row['status']!r}")

    try:
        quantity = int(row["quantity"])
        price = Decimal(row["price"])
    except (ValueError, InvalidOperation):
        raise ValueError("для delivered нужны целое quantity и числовое price")
    if quantity <= 0:
        raise ValueError("quantity должно быть положительным")
    if not price.is_finite() or price < 0:
        raise ValueError("price должно быть конечным неотрицательным числом")
    if price != price.quantize(Decimal("0.01")):
        raise ValueError("price должно содержать не более двух знаков после запятой")
    return quantity * price


def calculate(input_path):
    """Прочитать CSV, убрать повторы и собрать показатели по (sku, дата)."""
    totals = {}
    seen_orders = {}
    duplicates = 0

    with input_path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames is None or sorted(reader.fieldnames) != sorted(COLUMNS):
            raise ValueError("ожидаются колонки: " + ", ".join(COLUMNS))

        for row in reader:
            try:
                if None in row or None in row.values():
                    raise ValueError("число значений не совпадает с числом колонок")

                # Исправляем только однозначные различия в написании.
                row = {name: value.strip() for name, value in row.items()}
                row["status"] = row["status"].lower()
                if row["status"] == "canceled":
                    row["status"] = "cancelled"

                order_id = row["order_id"]
                if order_id in seen_orders:
                    if row != seen_orders[order_id]:
                        raise ValueError(f"заказ {order_id} повторяется с разными данными")
                    duplicates += 1
                    continue

                revenue = order_revenue(row)
                seen_orders[order_id] = row
                key = (row["sku"], row["order_date"])
                if key not in totals:
                    totals[key] = {"orders": 0, "revenue": Decimal("0")}
                totals[key]["orders"] += 1
                totals[key]["revenue"] += revenue
            except (ValueError, InvalidOperation) as error:
                raise ValueError(f"строка {reader.line_num}: {error}") from error

    return totals, duplicates


def write_result(output_path, totals):
    """Сохранить результат с сортировкой по артикулу и дате."""
    with output_path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.writer(target)
        writer.writerow(["sku", "order_date", "orders", "revenue"])
        for (sku, order_date), values in sorted(totals.items()):
            writer.writerow([
                sku, order_date, values["orders"], f"{values['revenue']:.2f}"
            ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path, default=Path("sales.csv"))
    parser.add_argument("-o", "--output", type=Path, default=Path("daily_by_sku.csv"))
    args = parser.parse_args()

    try:
        if args.input.resolve() == args.output.resolve():
            raise ValueError("входной и выходной файлы должны отличаться")
        # Сначала проверяем всю выгрузку, затем открываем выходной файл.
        totals, duplicates = calculate(args.input)
        write_result(args.output, totals)
    except (OSError, UnicodeError, csv.Error, ValueError) as error:
        parser.exit(1, f"Ошибка: {error}\n")

    print(f"Результат: {args.output}")
    print(f"Пропущено повторов: {duplicates}")
    print(f"Заказов: {sum(value['orders'] for value in totals.values())}")
    print(f"Выручка: {sum(value['revenue'] for value in totals.values()):.2f}")
    print(f"Строк результата: {len(totals)}")


if __name__ == "__main__":
    main()
