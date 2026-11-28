from datetime import date
from typing import Any

from Bizpoint.analytics.common.query import execute_query


def _validate_period(
    start_date: date | None,
    end_date: date | None,
) -> None:
    if start_date and end_date and start_date > end_date:
        raise ValueError("start_date cannot be later than end_date.")


def get_product_performance(
    dataset_version_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """
    Analyse product sales, discounts and completed returns.

    Sales are recognized on order_date.
    Returns are recognized on return_date.
    Discounts are stored as total order-line discounts.
    """

    if not dataset_version_id:
        raise ValueError("dataset_version_id is required.")

    _validate_period(start_date, end_date)

    parameters = {
        "dataset_version_id": dataset_version_id,
        "start_date": start_date,
        "end_date": end_date,
    }

    query = """
        WITH product_sales AS (
            SELECT
                soi.product_id,
                COUNT(DISTINCT soi.order_id) AS order_count,
                COUNT(soi.id) AS order_item_count,
                COALESCE(SUM(soi.quantity), 0) AS units_sold,

                COALESCE(
                    SUM(
                        soi.quantity::BIGINT
                        * soi.original_unit_price_cents
                    ),
                    0
                ) AS gross_sales_cents,

                COALESCE(
                    SUM(soi.discount_amount_cents),
                    0
                ) AS discount_amount_cents,

                COALESCE(
                    SUM(
                        soi.quantity::BIGINT
                        * soi.original_unit_price_cents
                        - soi.discount_amount_cents
                    ),
                    0
                ) AS net_sales_cents

            FROM sales_order_items soi
            JOIN sales_orders so
                ON so.id = soi.order_id
               AND so.dataset_version_id = soi.dataset_version_id

            WHERE soi.dataset_version_id = :dataset_version_id
              AND so.status = 'completed'
              AND (
                  CAST(:start_date AS DATE) IS NULL
                  OR so.order_date >= CAST(:start_date AS DATE)
              )
              AND (
                  CAST(:end_date AS DATE) IS NULL
                  OR so.order_date < CAST(:end_date AS DATE)
                      + INTERVAL '1 day'
              )

            GROUP BY soi.product_id
        ),

        product_returns AS (
            SELECT
                soi.product_id,
                COUNT(DISTINCT sr.id) AS return_count,
                COALESCE(SUM(sri.quantity), 0) AS units_returned,
                COALESCE(
                    SUM(sri.return_amount_cents),
                    0
                ) AS returned_amount_cents

            FROM sales_return_items sri
            JOIN sales_returns sr
                ON sr.id = sri.return_id
               AND sr.dataset_version_id = sri.dataset_version_id

            JOIN sales_order_items soi
                ON soi.id = sri.order_item_id
               AND soi.dataset_version_id = sri.dataset_version_id

            WHERE sri.dataset_version_id = :dataset_version_id
              AND sr.status = 'completed'
              AND (
                  CAST(:start_date AS DATE) IS NULL
                  OR sr.return_date >= CAST(:start_date AS DATE)
              )
              AND (
                  CAST(:end_date AS DATE) IS NULL
                  OR sr.return_date < CAST(:end_date AS DATE)
                      + INTERVAL '1 day'
              )

            GROUP BY soi.product_id
        ),

        product_activity AS (
            SELECT
                COALESCE(s.product_id, r.product_id) AS product_id,

                COALESCE(s.order_count, 0) AS order_count,
                COALESCE(s.order_item_count, 0) AS order_item_count,
                COALESCE(s.units_sold, 0) AS units_sold,
                COALESCE(s.gross_sales_cents, 0)
                    AS gross_sales_cents,
                COALESCE(s.discount_amount_cents, 0)
                    AS discount_amount_cents,
                COALESCE(s.net_sales_cents, 0)
                    AS net_sales_cents,

                COALESCE(r.return_count, 0) AS return_count,
                COALESCE(r.units_returned, 0) AS units_returned,
                COALESCE(r.returned_amount_cents, 0)
                    AS returned_amount_cents

            FROM product_sales s
            FULL OUTER JOIN product_returns r
                ON r.product_id = s.product_id
        )

        SELECT
            p.id AS product_id,
            p.sku,
            p.product_name,
            COALESCE(pc.category_name, 'Uncategorized')
                AS category_name,
            COALESCE(b.brand_name, 'Unbranded')
                AS brand_name,

            pa.order_count,
            pa.order_item_count,
            pa.units_sold,
            pa.gross_sales_cents,
            pa.discount_amount_cents,
            pa.net_sales_cents,

            pa.return_count,
            pa.units_returned,
            pa.returned_amount_cents,

            CASE
                WHEN pa.units_sold > 0
                THEN ROUND(
                    pa.units_returned::NUMERIC
                    / pa.units_sold * 100,
                    2
                )
                ELSE NULL
            END AS period_return_to_sales_percentage

        FROM product_activity pa

        JOIN products p
            ON p.id = pa.product_id
           AND p.dataset_version_id = :dataset_version_id

        LEFT JOIN product_categories pc
            ON pc.id = p.category_id
           AND pc.dataset_version_id = p.dataset_version_id

        LEFT JOIN brands b
            ON b.id = p.brand_id
           AND b.dataset_version_id = p.dataset_version_id

        ORDER BY pa.net_sales_cents DESC, p.product_name;
    """

    rows = execute_query(query, parameters)

    monetary_fields = (
        "gross_sales_cents",
        "discount_amount_cents",
        "net_sales_cents",
        "returned_amount_cents",
    )

    for row in rows:
        for field in monetary_fields:
            row[f"{field}_dollars"] = round(
                row[field] / 100,
                2,
            )

    # Calculate aggregate product metrics.
    summary = {
        "product_count": len(rows),
        "products_with_sales": sum(
            1 for row in rows if row["units_sold"] > 0
        ),
        "products_with_returns": sum(
            1 for row in rows if row["units_returned"] > 0
        ),
        "orders_containing_products": sum(
            row["order_count"] for row in rows
        ),
        "order_item_count": sum(
            row["order_item_count"] for row in rows
        ),
        "units_sold": sum(
            row["units_sold"] for row in rows
        ),
        "units_returned": sum(
            row["units_returned"] for row in rows
        ),
        "gross_sales_cents": sum(
            row["gross_sales_cents"] for row in rows
        ),
        "discount_amount_cents": sum(
            row["discount_amount_cents"] for row in rows
        ),
        "net_sales_cents": sum(
            row["net_sales_cents"] for row in rows
        ),
        "returned_amount_cents": sum(
            row["returned_amount_cents"] for row in rows
        ),
    }

    for field in monetary_fields:
        summary[f"{field}_dollars"] = round(
            summary[field] / 100,
            2,
        )

    summary["period_return_to_sales_percentage"] = (
        round(
            summary["units_returned"]
            / summary["units_sold"] * 100,
            2,
        )
        if summary["units_sold"] > 0
        else None
    )

    return {
        "dataset_version_id": dataset_version_id,
        "currency": "USD",
        "period": {
            "start_date": start_date,
            "end_date": end_date,
        },
        "summary": summary,
        "products": rows,
    }
