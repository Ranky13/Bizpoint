from datetime import date
from typing import Any

from Bizpoint.analytics.common.query import execute_query


def get_inventory_performance(
    dataset_version_id: str,
    as_of_date: date | None = None,
) -> dict[str, Any]:
    """
    Calculate inventory quantities and valuation from inventory movements.

    Stock quantity:
        purchase_receipt  -> increases stock
        customer_return   -> increases stock
        sale              -> decreases stock

    Inventory valuation:
        Receipt cost and returned inventory cost are added.
        Sale cost is deducted.

    The recorded movement unit cost is used. Sale movement costs have
    already been validated against the moving weighted-average cost audit.

    If as_of_date is provided, the result includes movements up to and
    including that date. Otherwise, all available movements are included.
    """

    if not dataset_version_id or not isinstance(dataset_version_id, str):
        raise ValueError("A valid dataset_version_id is required.")

    if as_of_date is not None and not isinstance(as_of_date, date):
        raise TypeError("as_of_date must be a datetime.date or None.")

    query = """
        SELECT
            p.id AS product_id,
            p.sku,
            p.product_name,
            p.product_status,
            p.is_active AS product_is_active,

            s.id AS store_id,
            s.store_name,
            s.store_code,
            s.is_active AS store_is_active,

            SUM(
                CASE
                    WHEN im.movement_type IN (
                        'purchase_receipt',
                        'customer_return'
                    )
                    THEN im.quantity
                    WHEN im.movement_type = 'sale'
                    THEN im.quantity
                    ELSE 0
                END
            ) AS on_hand_quantity,

            SUM(
                CASE
                    WHEN im.movement_type IN (
                        'purchase_receipt',
                        'customer_return'
                    )
                    THEN ABS(im.quantity::BIGINT) * im.unit_cost_cents
                    WHEN im.movement_type = 'sale'
                    THEN -(
                        ABS(im.quantity::BIGINT) * im.unit_cost_cents
                    )
                    ELSE 0
                END
            ) AS inventory_value_cents,

            COUNT(*) AS movement_count,

            COUNT(*) FILTER (
                WHERE im.movement_type = 'purchase_receipt'
            ) AS receipt_count,

            COUNT(*) FILTER (
                WHERE im.movement_type = 'sale'
            ) AS sale_count,

            COUNT(*) FILTER (
                WHERE im.movement_type = 'customer_return'
            ) AS return_count

        FROM inventory_movements im

        INNER JOIN products p
            ON p.id = im.product_id
            AND p.dataset_version_id = im.dataset_version_id

        INNER JOIN stores s
            ON s.id = im.store_id
            AND s.dataset_version_id = im.dataset_version_id

        WHERE im.dataset_version_id = :dataset_version_id
          AND (
              CAST(:as_of_date AS DATE) IS NULL
              OR im.movement_date
                 < CAST(:as_of_date AS DATE) + INTERVAL '1 day'
          )

        GROUP BY
            p.id,
            p.sku,
            p.product_name,
            p.product_status,
            p.is_active,
            s.id,
            s.store_name,
            s.store_code,
            s.is_active

        ORDER BY
            p.product_name,
            s.store_name
    """

    rows = execute_query(
        query,
        {
            "dataset_version_id": dataset_version_id,
            "as_of_date": as_of_date,
        },
    )

    product_totals: dict[str, dict[str, Any]] = {}
    store_totals: dict[str, dict[str, Any]] = {}

    total_units = 0
    total_value_cents = 0
    total_movements = 0
    total_receipts = 0
    total_sales = 0
    total_returns = 0

    negative_stock_positions = 0
    zero_stock_positions = 0

    product_store_details = []

    for row in rows:
        quantity = int(row["on_hand_quantity"] or 0)
        value_cents = int(row["inventory_value_cents"] or 0)

        movement_count = int(row["movement_count"] or 0)
        receipt_count = int(row["receipt_count"] or 0)
        sale_count = int(row["sale_count"] or 0)
        return_count = int(row["return_count"] or 0)

        product_id = row["product_id"]
        store_id = row["store_id"]

        total_units += quantity
        total_value_cents += value_cents
        total_movements += movement_count
        total_receipts += receipt_count
        total_sales += sale_count
        total_returns += return_count

        if quantity < 0:
            negative_stock_positions += 1
        elif quantity == 0:
            zero_stock_positions += 1

        if product_id not in product_totals:
            product_totals[product_id] = {
                "product_id": product_id,
                "sku": row["sku"],
                "product_name": row["product_name"],
                "product_status": row["product_status"],
                "is_active": row["product_is_active"],
                "store_count": 0,
                "on_hand_quantity": 0,
                "inventory_value_cents": 0,
                "movement_count": 0,
            }

        product = product_totals[product_id]
        product["store_count"] += 1
        product["on_hand_quantity"] += quantity
        product["inventory_value_cents"] += value_cents
        product["movement_count"] += movement_count

        if store_id not in store_totals:
            store_totals[store_id] = {
                "store_id": store_id,
                "store_name": row["store_name"],
                "store_code": row["store_code"],
                "is_active": row["store_is_active"],
                "product_count": 0,
                "on_hand_quantity": 0,
                "inventory_value_cents": 0,
                "movement_count": 0,
            }

        store = store_totals[store_id]
        store["product_count"] += 1
        store["on_hand_quantity"] += quantity
        store["inventory_value_cents"] += value_cents
        store["movement_count"] += movement_count

        product_store_details.append({
            "product_id": product_id,
            "sku": row["sku"],
            "product_name": row["product_name"],
            "store_id": store_id,
            "store_name": row["store_name"],
            "on_hand_quantity": quantity,
            "inventory_value_cents": value_cents,
            "inventory_value_dollars": round(
                value_cents / 100, 2
            ),
            "movement_count": movement_count,
            "receipt_count": receipt_count,
            "sale_count": sale_count,
            "return_count": return_count,
        })

    products = list(product_totals.values())
    stores = list(store_totals.values())

    for item in products + stores:
        item["inventory_value_dollars"] = round(
            item["inventory_value_cents"] / 100, 2
        )

    products.sort(
        key=lambda item: item["inventory_value_cents"],
        reverse=True,
    )

    stores.sort(
        key=lambda item: item["inventory_value_cents"],
        reverse=True,
    )

    product_value_total = sum(
        item["inventory_value_cents"] for item in products
    )

    store_value_total = sum(
        item["inventory_value_cents"] for item in stores
    )

    product_quantity_total = sum(
        item["on_hand_quantity"] for item in products
    )

    store_quantity_total = sum(
        item["on_hand_quantity"] for item in stores
    )

    reconciliation = {
        "product_inventory_value_matches_total": (
            product_value_total == total_value_cents
        ),
        "store_inventory_value_matches_total": (
            store_value_total == total_value_cents
        ),
        "product_quantities_match_total": (
            product_quantity_total == total_units
        ),
        "store_quantities_match_total": (
            store_quantity_total == total_units
        ),
        "movement_counts_match_total": (
            total_receipts + total_sales + total_returns
            == total_movements
        ),
    }

    reconciliation["all_checks_passed"] = all(
        reconciliation.values()
    )

    return {
        "metadata": {
            "dataset_version_id": dataset_version_id,
            "as_of_date": (
                as_of_date.isoformat()
                if as_of_date is not None
                else None
            ),
            "currency": "USD",
            "valuation_method": "Weighted average",
            "valuation_basis": "Recorded inventory movement unit costs",
        },
        "summary": {
            "product_count": len(products),
            "store_count": len(stores),
            "product_store_count": len(product_store_details),
            "total_units_on_hand": total_units,
            "total_inventory_value_cents": total_value_cents,
            "total_inventory_value_dollars": round(
                total_value_cents / 100, 2
            ),
            "total_movements": total_movements,
            "purchase_receipt_movements": total_receipts,
            "sale_movements": total_sales,
            "customer_return_movements": total_returns,
            "negative_stock_positions": negative_stock_positions,
            "zero_stock_positions": zero_stock_positions,
        },
        "by_product": products,
        "by_store": stores,
        "by_product_store": product_store_details,
        "reconciliation": reconciliation,
    }
