from datetime import date
from typing import Any

from Bizpoint.analytics.common.query import execute_query


def get_store_inventory_performance(
    dataset_version_id: str,
    as_of_date: date | None = None,
) -> dict[str, Any]:
    """
    Analyse inventory quantities, valuation and movements by store.

    Stores without inventory movements are retained in the results.
    Inventory value is reconstructed from recorded movement costs.
    """

    if not dataset_version_id or not isinstance(dataset_version_id, str):
        raise ValueError("A valid dataset_version_id is required.")

    if as_of_date is not None and not isinstance(as_of_date, date):
        raise TypeError("as_of_date must be a datetime.date or None.")

    query = """
        SELECT
            s.id AS store_id,
            s.store_name,
            s.store_code,
            s.is_active,

            COUNT(DISTINCT im.product_id) AS products_with_movements,

            COALESCE(SUM(
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
            ), 0) AS on_hand_quantity,

            COALESCE(SUM(
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
            ), 0) AS inventory_value_cents,

            COUNT(im.id) AS movement_count,

            COUNT(im.id) FILTER (
                WHERE im.movement_type = 'purchase_receipt'
            ) AS receipt_count,

            COUNT(im.id) FILTER (
                WHERE im.movement_type = 'sale'
            ) AS sale_count,

            COUNT(im.id) FILTER (
                WHERE im.movement_type = 'customer_return'
            ) AS return_count,

            COALESCE(SUM(
                CASE
                    WHEN im.movement_type = 'purchase_receipt'
                    THEN im.quantity
                    ELSE 0
                END
            ), 0) AS units_received,

            COALESCE(SUM(
                CASE
                    WHEN im.movement_type = 'sale'
                    THEN ABS(im.quantity::BIGINT)
                    ELSE 0
                END
            ), 0) AS units_sold,

            COALESCE(SUM(
                CASE
                    WHEN im.movement_type = 'customer_return'
                    THEN im.quantity
                    ELSE 0
                END
            ), 0) AS units_returned

        FROM stores s

        LEFT JOIN inventory_movements im
            ON im.store_id = s.id
            AND im.dataset_version_id = s.dataset_version_id
            AND (
                CAST(:as_of_date AS DATE) IS NULL
                OR im.movement_date
                   < CAST(:as_of_date AS DATE) + INTERVAL '1 day'
            )

        WHERE s.dataset_version_id = :dataset_version_id

        GROUP BY
            s.id,
            s.store_name,
            s.store_code,
            s.is_active

        ORDER BY inventory_value_cents DESC, s.store_name
    """

    rows = execute_query(
        query,
        {
            "dataset_version_id": dataset_version_id,
            "as_of_date": as_of_date,
        },
    )

    stores = []

    for row in rows:
        item = dict(row)

        integer_fields = (
            "products_with_movements",
            "on_hand_quantity",
            "inventory_value_cents",
            "movement_count",
            "receipt_count",
            "sale_count",
            "return_count",
            "units_received",
            "units_sold",
            "units_returned",
        )

        for field in integer_fields:
            item[field] = int(item[field] or 0)

        item["inventory_value_dollars"] = round(
            item["inventory_value_cents"] / 100, 2
        )

        item["stock_status"] = (
            "negative_stock"
            if item["on_hand_quantity"] < 0
            else "out_of_stock"
            if item["on_hand_quantity"] == 0
            else "in_stock"
        )

        stores.append(item)

    total_units = sum(
        item["on_hand_quantity"] for item in stores
    )

    total_value_cents = sum(
        item["inventory_value_cents"] for item in stores
    )

    total_movements = sum(
        item["movement_count"] for item in stores
    )

    total_receipts = sum(
        item["receipt_count"] for item in stores
    )

    total_sales = sum(
        item["sale_count"] for item in stores
    )

    total_returns = sum(
        item["return_count"] for item in stores
    )

    total_units_received = sum(
        item["units_received"] for item in stores
    )

    total_units_sold = sum(
        item["units_sold"] for item in stores
    )

    total_units_returned = sum(
        item["units_returned"] for item in stores
    )

    summary = {
        "store_count": len(stores),
        "stores_with_stock": sum(
            item["on_hand_quantity"] > 0 for item in stores
        ),
        "stores_without_stock": sum(
            item["on_hand_quantity"] == 0 for item in stores
        ),
        "stores_with_negative_stock": sum(
            item["on_hand_quantity"] < 0 for item in stores
        ),
        "total_units_on_hand": total_units,
        "total_inventory_value_cents": total_value_cents,
        "total_inventory_value_dollars": round(
            total_value_cents / 100, 2
        ),
        "total_movements": total_movements,
        "total_receipt_movements": total_receipts,
        "total_sale_movements": total_sales,
        "total_return_movements": total_returns,
        "total_units_received": total_units_received,
        "total_units_sold": total_units_sold,
        "total_units_returned": total_units_returned,
    }

    reconciliation = {
        "store_inventory_value_reconciles": (
            total_value_cents
            == sum(
                item["inventory_value_cents"] for item in stores
            )
        ),
        "store_stock_quantity_reconciles": (
            total_units
            == total_units_received
            + total_units_returned
            - total_units_sold
        ),
        "movement_counts_reconcile": (
            total_movements
            == total_receipts + total_sales + total_returns
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
        },
        "summary": summary,
        "stores": stores,
        "top_stores_by_inventory_value": stores[:10],
        "reconciliation": reconciliation,
    }
