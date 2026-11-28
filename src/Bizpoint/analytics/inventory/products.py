from datetime import date
from typing import Any

from Bizpoint.analytics.common.query import execute_query


def get_inventory_product_performance(
    dataset_version_id: str,
    as_of_date: date | None = None,
) -> dict[str, Any]:
    """
    Analyse inventory position and movement activity by product.

    Stock on hand is reconstructed from all movements up to as_of_date.
    Inventory value uses the recorded movement unit costs.
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
            p.is_active,
            pc.category_name,
            b.brand_name,

            COUNT(DISTINCT im.store_id) FILTER (
                WHERE im.id IS NOT NULL
            ) AS store_count,

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

        FROM products p

        LEFT JOIN product_categories pc
            ON pc.id = p.category_id
            AND pc.dataset_version_id = p.dataset_version_id

        LEFT JOIN brands b
            ON b.id = p.brand_id
            AND b.dataset_version_id = p.dataset_version_id

        LEFT JOIN inventory_movements im
            ON im.product_id = p.id
            AND im.dataset_version_id = p.dataset_version_id
            AND (
                CAST(:as_of_date AS DATE) IS NULL
                OR im.movement_date
                   < CAST(:as_of_date AS DATE) + INTERVAL '1 day'
            )

        WHERE p.dataset_version_id = :dataset_version_id

        GROUP BY
            p.id,
            p.sku,
            p.product_name,
            p.product_status,
            p.is_active,
            pc.category_name,
            b.brand_name

        ORDER BY inventory_value_cents DESC, p.product_name
    """

    rows = execute_query(
        query,
        {
            "dataset_version_id": dataset_version_id,
            "as_of_date": as_of_date,
        },
    )

    products = []

    for row in rows:
        item = dict(row)

        for field in (
            "store_count",
            "on_hand_quantity",
            "inventory_value_cents",
            "movement_count",
            "receipt_count",
            "sale_count",
            "return_count",
            "units_received",
            "units_sold",
            "units_returned",
        ):
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

        item["return_to_sales_unit_percentage"] = (
            round(
                item["units_returned"] / item["units_sold"] * 100,
                2,
            )
            if item["units_sold"] > 0
            else None
        )

        products.append(item)

    summary = {
        "product_count": len(products),
        "products_in_stock": sum(
            item["on_hand_quantity"] > 0 for item in products
        ),
        "products_out_of_stock": sum(
            item["on_hand_quantity"] == 0 for item in products
        ),
        "products_with_negative_stock": sum(
            item["on_hand_quantity"] < 0 for item in products
        ),
        "total_units_on_hand": sum(
            item["on_hand_quantity"] for item in products
        ),
        "total_inventory_value_cents": sum(
            item["inventory_value_cents"] for item in products
        ),
        "total_inventory_value_dollars": round(
            sum(item["inventory_value_cents"] for item in products)
            / 100,
            2,
        ),
        "total_units_received": sum(
            item["units_received"] for item in products
        ),
        "total_units_sold": sum(
            item["units_sold"] for item in products
        ),
        "total_units_returned": sum(
            item["units_returned"] for item in products
        ),
        "total_movements": sum(
            item["movement_count"] for item in products
        ),
    }

    reconciliation = {
        "product_inventory_value_reconciles": (
            summary["total_inventory_value_cents"]
            == sum(
                item["inventory_value_cents"] for item in products
            )
        ),
        "product_stock_quantity_reconciles": (
            summary["total_units_on_hand"]
            == summary["total_units_received"]
            + summary["total_units_returned"]
            - summary["total_units_sold"]
        ),
        "movement_counts_reconcile": (
            summary["total_movements"]
            == sum(
                item["receipt_count"]
                + item["sale_count"]
                + item["return_count"]
                for item in products
            )
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
        "products": products,
        "top_products_by_inventory_value": products[:10],
        "reconciliation": reconciliation,
    }
