
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import text

from Bizpoint.database.connection import engine
from Bizpoint.data_generation.config import DATASET_NAME


def round_to_cent(value):
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def main():
    with engine.connect() as connection:

        dataset_id = connection.execute(
            text("""
                SELECT id
                FROM datasets
                WHERE name = :dataset_name
            """),
            {"dataset_name": DATASET_NAME},
        ).scalar_one_or_none()

        if dataset_id is None:
            raise RuntimeError("Configured dataset was not found.")

        version_id = connection.execute(
            text("""
                SELECT id
                FROM dataset_versions
                WHERE dataset_id = :dataset_id
                  AND version_number = 1
            """),
            {"dataset_id": dataset_id},
        ).scalar_one_or_none()

        if version_id is None:
            raise RuntimeError("Dataset version 1 was not found.")

        movements = connection.execute(
            text("""
                SELECT
                    id,
                    product_id,
                    store_id,
                    movement_type,
                    quantity,
                    unit_cost_cents,
                    movement_date,
                    created_at
                FROM inventory_movements
                WHERE dataset_version_id = :version_id
                ORDER BY
                    product_id,
                    store_id,
                    movement_date,
                    created_at,
                    id
            """),
            {"version_id": version_id},
        ).mappings().all()

    # Each product/store combination has its own inventory valuation.
    inventory = defaultdict(
        lambda: {
            "quantity": 0,
            "value_cents": Decimal("0"),
        }
    )

    failures = []
    processed = 0

    for movement in movements:

        key = (
            movement["product_id"],
            movement["store_id"],
        )

        stock = inventory[key]

        movement_type = movement["movement_type"]
        quantity = movement["quantity"]
        unit_cost = movement["unit_cost_cents"]

        if unit_cost < 0:
            failures.append(
                f"Negative unit cost in movement {movement['id']}"
            )
            continue

        cost = Decimal(unit_cost)

        # Stock entering inventory.
        if movement_type in (
            "purchase_receipt",
            "customer_return",
            "opening_stock",
        ):
            if quantity <= 0:
                failures.append(
                    f"Invalid incoming quantity: {movement['id']}"
                )
                continue

            stock["quantity"] += quantity
            stock["value_cents"] += Decimal(quantity) * cost

        # Stock leaving inventory.
        elif movement_type == "sale":

            issued_quantity = abs(quantity)

            if issued_quantity <= 0:
                failures.append(
                    f"Invalid sale quantity: {movement['id']}"
                )
                continue

            if stock["quantity"] < issued_quantity:
                failures.append(
                    f"Insufficient stock for sale movement "
                    f"{movement['id']}"
                )
                continue

            if stock["quantity"] == 0:
                failures.append(
                    f"Zero stock before sale: {movement['id']}"
                )
                continue

            weighted_average = (
                stock["value_cents"]
                / Decimal(stock["quantity"])
            )

            expected_unit_cost = round_to_cent(weighted_average)

            if Decimal(unit_cost) != expected_unit_cost:
                failures.append(
                    f"Sale cost mismatch | movement={movement['id']} "
                    f"| recorded={unit_cost} cents "
                    f"| expected={expected_unit_cost} cents"
                )

            # Reduce inventory using the calculated weighted average,
            # not the potentially incorrect recorded sale cost.
            stock["quantity"] -= issued_quantity

            stock["value_cents"] -= (
                Decimal(issued_quantity) * weighted_average
            )

            if stock["quantity"] == 0:
                stock["value_cents"] = Decimal("0")

        else:
            failures.append(
                f"Unsupported movement type: {movement_type} "
                f"| movement={movement['id']}"
            )
            continue

        processed += 1

    total_quantity = sum(
        stock["quantity"] for stock in inventory.values()
    )

    total_value_cents = sum(
        (
            stock["value_cents"]
            for stock in inventory.values()
        ),
        Decimal("0"),
    )

    negative_balances = sum(
        1
        for stock in inventory.values()
        if stock["quantity"] < 0
    )

    print("\nWEIGHTED-AVERAGE INVENTORY VALUATION AUDIT")
    print("=" * 65)
    print(f"Dataset: {DATASET_NAME}")
    print(f"Dataset version: 1")
    print(f"Movements processed: {processed}")
    print(f"Product/store combinations: {len(inventory)}")

    print("\nENDING INVENTORY")
    print("-" * 65)
    print(f"Total units on hand: {total_quantity}")
    print(
        "Total inventory value: "
        f"${total_value_cents / Decimal('100'):,.2f}"
    )
    print(f"Negative stock balances: {negative_balances}")

    print("\nVALUATION CHECKS")
    print("-" * 65)
    print(
        "Sale unit-cost mismatches: "
        f"{sum('Sale cost mismatch' in item for item in failures)}"
    )
    print(
        "Other audit issues: "
        f"{sum('Sale cost mismatch' not in item for item in failures)}"
    )

    if failures:
        print("\nISSUES FOUND")
        print("-" * 65)

        for failure in failures[:30]:
            print(failure)

        if len(failures) > 30:
            print(
                f"... and {len(failures) - 30} additional issues."
            )

        print("\nRESULT: VALUATION AUDIT FAILED")
    else:
        print("\nRESULT: WEIGHTED-AVERAGE VALUATION PASSED")

    print("=" * 65)


if __name__ == "__main__":
    main()
