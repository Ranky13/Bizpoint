from datetime import date
from decimal import Decimal
from typing import Any

from Bizpoint.analytics.common.query import execute_query


def get_customer_lifetime_value(
    dataset_version_id: str,
) -> dict[str, Any]:
    """
    Calculate historical customer lifetime value.

    CLV is calculated as completed sales revenue less completed
    sales returns linked to the customer's original orders.

    This is historical net revenue, not a prediction of future value.
    """

    if not dataset_version_id:
        raise ValueError("dataset_version_id is required")

    parameters = {
        "dataset_version_id": dataset_version_id,
    }

    customer_query = """
        WITH completed_orders AS (
            SELECT
                customer_id,
                COUNT(id) AS completed_orders,
                SUM(total_amount_cents) AS gross_revenue_cents,
                MIN(order_date)::DATE AS first_order_date,
                MAX(order_date)::DATE AS last_order_date
            FROM sales_orders
            WHERE dataset_version_id = :dataset_version_id
              AND status = 'completed'
            GROUP BY customer_id
        ),

        completed_returns AS (
            SELECT
                so.customer_id,
                COUNT(DISTINCT sr.id) AS completed_returns,
                SUM(sri.return_amount_cents) AS returned_amount_cents
            FROM sales_returns sr

            JOIN sales_orders so
                ON so.id = sr.order_id
               AND so.dataset_version_id = sr.dataset_version_id

            JOIN sales_return_items sri
                ON sri.return_id = sr.id
               AND sri.dataset_version_id = sr.dataset_version_id

            WHERE sr.dataset_version_id = :dataset_version_id
              AND sr.status = 'completed'
              AND so.status = 'completed'

            GROUP BY so.customer_id
        ),

        analysis_reference AS (
            SELECT MAX(order_date)::DATE AS analysis_date
            FROM sales_orders
            WHERE dataset_version_id = :dataset_version_id
              AND status = 'completed'
        )

        SELECT
            c.id AS customer_id,
            c.customer_code,

            COALESCE(
                NULLIF(c.business_name, ''),
                NULLIF(
                    CONCAT_WS(' ', c.first_name, c.last_name),
                    ''
                ),
                c.customer_code
            ) AS customer_name,

            c.customer_type,
            cs.segment_name,
            r.region_name,
            c.registration_date,

            COALESCE(o.completed_orders, 0) AS completed_orders,
            COALESCE(o.gross_revenue_cents, 0) AS gross_revenue_cents,

            COALESCE(ret.completed_returns, 0) AS completed_returns,
            COALESCE(ret.returned_amount_cents, 0)
                AS returned_amount_cents,

            COALESCE(o.gross_revenue_cents, 0)
                - COALESCE(ret.returned_amount_cents, 0)
                AS net_lifetime_revenue_cents,

            o.first_order_date,
            o.last_order_date,
            ar.analysis_date,

            CASE
                WHEN o.completed_orders > 0
                THEN ROUND(
                    o.gross_revenue_cents::NUMERIC
                    / o.completed_orders,
                    2
                )
                ELSE 0
            END AS average_order_value_cents,

            CASE
                WHEN o.first_order_date IS NOT NULL
                THEN (
                    o.last_order_date - o.first_order_date
                )
                ELSE NULL
            END AS purchase_lifespan_days,

            CASE
                WHEN o.last_order_date IS NOT NULL
                THEN (
                    ar.analysis_date - o.last_order_date
                )
                ELSE NULL
            END AS days_since_last_purchase

        FROM customers c

        CROSS JOIN analysis_reference ar

        LEFT JOIN completed_orders o
            ON o.customer_id = c.id

        LEFT JOIN completed_returns ret
            ON ret.customer_id = c.id

        LEFT JOIN customer_segments cs
            ON cs.id = c.segment_id
           AND cs.dataset_version_id = c.dataset_version_id

        LEFT JOIN regions r
            ON r.id = c.region_id
           AND r.dataset_version_id = c.dataset_version_id

        WHERE c.dataset_version_id = :dataset_version_id

        ORDER BY
            net_lifetime_revenue_cents DESC,
            completed_orders DESC,
            c.customer_code
    """

    rows = execute_query(customer_query, parameters)

    customers = []

    for row in rows:
        gross_cents = int(row["gross_revenue_cents"] or 0)
        returned_cents = int(row["returned_amount_cents"] or 0)
        net_cents = int(row["net_lifetime_revenue_cents"] or 0)
        orders = int(row["completed_orders"] or 0)
        average_order_cents = Decimal(
            str(row["average_order_value_cents"] or 0)
        )

        customers.append({
            "customer_id": row["customer_id"],
            "customer_code": row["customer_code"],
            "customer_name": row["customer_name"],
            "customer_type": row["customer_type"],
            "customer_segment": row["segment_name"],
            "region": row["region_name"],
            "registration_date": row["registration_date"],
            "completed_orders": orders,
            "completed_returns": int(
                row["completed_returns"] or 0
            ),
            "gross_revenue_cents": gross_cents,
            "gross_revenue_dollars": round(gross_cents / 100, 2),
            "returned_amount_cents": returned_cents,
            "returned_amount_dollars": round(
                returned_cents / 100,
                2,
            ),
            "net_lifetime_revenue_cents": net_cents,
            "net_lifetime_revenue_dollars": round(
                net_cents / 100,
                2,
            ),
            "average_order_value_cents": average_order_cents,
            "average_order_value_dollars": round(
                float(average_order_cents) / 100,
                2,
            ),
            "first_order_date": row["first_order_date"],
            "last_order_date": row["last_order_date"],
            "analysis_date": row["analysis_date"],
            "purchase_lifespan_days": row[
                "purchase_lifespan_days"
            ],
            "days_since_last_purchase": row[
                "days_since_last_purchase"
            ],
            "has_purchased": orders > 0,
        })

    purchasing_customers = [
        customer
        for customer in customers
        if customer["has_purchased"]
    ]

    total_customers = len(customers)
    purchasing_count = len(purchasing_customers)

    total_orders = sum(
        customer["completed_orders"]
        for customer in customers
    )

    total_gross_cents = sum(
        customer["gross_revenue_cents"]
        for customer in customers
    )

    total_returns_cents = sum(
        customer["returned_amount_cents"]
        for customer in customers
    )

    total_net_cents = sum(
        customer["net_lifetime_revenue_cents"]
        for customer in customers
    )

    total_completed_returns = sum(
        customer["completed_returns"]
        for customer in customers
    )

    average_clv_purchasers = (
        total_net_cents / purchasing_count
        if purchasing_count else 0
    )

    average_clv_all_customers = (
        total_net_cents / total_customers
        if total_customers else 0
    )

    segment_totals = {}

    for customer in customers:
        segment = customer["customer_segment"] or "Unassigned"

        if segment not in segment_totals:
            segment_totals[segment] = {
                "customer_count": 0,
                "purchasing_customers": 0,
                "completed_orders": 0,
                "gross_revenue_cents": 0,
                "returned_amount_cents": 0,
                "net_lifetime_revenue_cents": 0,
            }

        item = segment_totals[segment]

        item["customer_count"] += 1
        item["purchasing_customers"] += int(
            customer["has_purchased"]
        )
        item["completed_orders"] += customer["completed_orders"]
        item["gross_revenue_cents"] += (
            customer["gross_revenue_cents"]
        )
        item["returned_amount_cents"] += (
            customer["returned_amount_cents"]
        )
        item["net_lifetime_revenue_cents"] += (
            customer["net_lifetime_revenue_cents"]
        )

    segments = []

    for segment, values in segment_totals.items():
        purchaser_count = values["purchasing_customers"]
        net_cents = values["net_lifetime_revenue_cents"]

        segments.append({
            "segment": segment,
            **values,
            "gross_revenue_dollars": round(
                values["gross_revenue_cents"] / 100,
                2,
            ),
            "returned_amount_dollars": round(
                values["returned_amount_cents"] / 100,
                2,
            ),
            "net_lifetime_revenue_dollars": round(
                net_cents / 100,
                2,
            ),
            "average_clv_per_purchasing_customer": round(
                net_cents / purchaser_count / 100,
                2,
            ) if purchaser_count else 0,
        })

    segments.sort(
        key=lambda item: item["net_lifetime_revenue_cents"],
        reverse=True,
    )

    analysis_date = (
        customers[0]["analysis_date"] if customers else None
    )

    return {
        "dataset_version_id": dataset_version_id,
        "analysis_date": analysis_date,
        "summary": {
            "total_customers": total_customers,
            "purchasing_customers": purchasing_count,
            "non_purchasing_customers": (
                total_customers - purchasing_count
            ),
            "customer_purchase_rate": round(
                purchasing_count / total_customers * 100,
                2,
            ) if total_customers else 0,
            "completed_orders": total_orders,
            "completed_returns": total_completed_returns,
            "gross_revenue_cents": total_gross_cents,
            "gross_revenue_dollars": round(
                total_gross_cents / 100,
                2,
            ),
            "returned_amount_cents": total_returns_cents,
            "returned_amount_dollars": round(
                total_returns_cents / 100,
                2,
            ),
            "net_lifetime_revenue_cents": total_net_cents,
            "net_lifetime_revenue_dollars": round(
                total_net_cents / 100,
                2,
            ),
            "average_clv_per_purchasing_customer": round(
                average_clv_purchasers / 100,
                2,
            ),
            "average_clv_per_registered_customer": round(
                average_clv_all_customers / 100,
                2,
            ),
        },
        "by_segment": segments,
        "customers": customers,
        "top_customers": [
            customer
            for customer in customers
            if customer["has_purchased"]
        ][:20],
    }
