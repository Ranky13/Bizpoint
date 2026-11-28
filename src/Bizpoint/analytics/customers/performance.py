from datetime import date
from decimal import Decimal
from typing import Any

from Bizpoint.analytics.common.query import execute_query


def _to_dollars(amount_cents: int | Decimal | None) -> float:
    return round(float(amount_cents or 0) / 100, 2)


def _to_percentage(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0

    return round((numerator / denominator) * 100, 2)


def _validate_period(
    start_date: date | None,
    end_date: date | None,
) -> None:
    if start_date and end_date and start_date > end_date:
        raise ValueError("start_date cannot be later than end_date")


def get_customer_performance(
    dataset_version_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """
    Analyse customer purchasing performance for one dataset version.

    Customer records are retained even when they have no completed orders.
    Sales are recognised using completed sales orders and order_date.
    """

    if not dataset_version_id:
        raise ValueError("dataset_version_id is required")

    _validate_period(start_date, end_date)

    parameters = {
        "dataset_version_id": dataset_version_id,
        "start_date": start_date,
        "end_date": end_date,
    }

    customer_query = """
        WITH customer_sales AS (
            SELECT
                so.customer_id,
                COUNT(so.id) AS completed_orders,
                SUM(so.total_amount_cents) AS gross_revenue_cents,
                MIN(so.order_date) AS first_order_date,
                MAX(so.order_date) AS last_order_date
            FROM sales_orders so
            WHERE so.dataset_version_id = :dataset_version_id
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
            GROUP BY so.customer_id
        )
        SELECT
            c.id AS customer_id,
            c.customer_code,
            COALESCE(
                NULLIF(c.business_name, ''),
                NULLIF(
                    TRIM(CONCAT_WS(' ', c.first_name, c.last_name)),
                    ''
                ),
                c.customer_code
            ) AS customer_name,
            c.customer_type,
            c.status AS customer_status,
            c.registration_date,
            c.region_id,
            r.region_name,
            c.segment_id,
            cs.segment_name,
            COALESCE(s.completed_orders, 0) AS completed_orders,
            COALESCE(s.gross_revenue_cents, 0) AS gross_revenue_cents,
            s.first_order_date,
            s.last_order_date
        FROM customers c
        LEFT JOIN customer_sales s
            ON s.customer_id = c.id
        LEFT JOIN customer_segments cs
            ON cs.id = c.segment_id
           AND cs.dataset_version_id = c.dataset_version_id
        LEFT JOIN regions r
            ON r.id = c.region_id
           AND r.dataset_version_id = c.dataset_version_id
        WHERE c.dataset_version_id = :dataset_version_id
        ORDER BY
            COALESCE(s.gross_revenue_cents, 0) DESC,
            c.customer_code
    """

    customers = execute_query(customer_query, parameters)

    monthly_query = """
        SELECT
            DATE_TRUNC('month', so.order_date)::DATE AS month,
            COUNT(so.id) AS completed_orders,
            COUNT(DISTINCT so.customer_id) AS unique_customers,
            SUM(so.total_amount_cents) AS gross_revenue_cents
        FROM sales_orders so
        WHERE so.dataset_version_id = :dataset_version_id
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
        GROUP BY DATE_TRUNC('month', so.order_date)
        ORDER BY month
    """

    monthly_rows = execute_query(monthly_query, parameters)

    customer_count = len(customers)

    customers_with_sales = sum(
        1 for customer in customers
        if customer["completed_orders"] > 0
    )

    repeat_customers = sum(
        1 for customer in customers
        if customer["completed_orders"] > 1
    )

    one_time_customers = sum(
        1 for customer in customers
        if customer["completed_orders"] == 1
    )

    total_orders = sum(
        int(customer["completed_orders"])
        for customer in customers
    )

    total_revenue_cents = sum(
        int(customer["gross_revenue_cents"] or 0)
        for customer in customers
    )

    customer_rows = []

    for customer in customers:
        completed_orders = int(customer["completed_orders"])
        revenue_cents = int(customer["gross_revenue_cents"] or 0)

        customer_rows.append({
            **customer,
            "completed_orders": completed_orders,
            "gross_revenue_cents": revenue_cents,
            "gross_revenue_dollars": _to_dollars(revenue_cents),
            "average_order_value_cents": (
                round(revenue_cents / completed_orders, 2)
                if completed_orders else 0
            ),
            "average_order_value_dollars": (
                round(revenue_cents / completed_orders / 100, 2)
                if completed_orders else 0
            ),
            "customer_type": customer["customer_type"],
            "customer_status": customer["customer_status"],
            "purchase_frequency": (
                "repeat"
                if completed_orders > 1
                else "one_time"
                if completed_orders == 1
                else "no_purchase"
            ),
        })

    def aggregate_by(field: str) -> list[dict[str, Any]]:
        groups: dict[str, dict[str, Any]] = {}

        for customer in customer_rows:
            group_name = customer[field] or "Unassigned"

            if group_name not in groups:
                groups[group_name] = {
                    "name": group_name,
                    "customer_count": 0,
                    "customers_with_sales": 0,
                    "repeat_customers": 0,
                    "completed_orders": 0,
                    "gross_revenue_cents": 0,
                }

            group = groups[group_name]
            orders = customer["completed_orders"]

            group["customer_count"] += 1
            group["completed_orders"] += orders
            group["gross_revenue_cents"] += customer[
                "gross_revenue_cents"
            ]

            if orders > 0:
                group["customers_with_sales"] += 1

            if orders > 1:
                group["repeat_customers"] += 1

        results = []

        for group in groups.values():
            revenue_cents = group["gross_revenue_cents"]

            group["gross_revenue_dollars"] = _to_dollars(
                revenue_cents
            )
            group["average_order_value_dollars"] = (
                round(
                    revenue_cents / group["completed_orders"] / 100,
                    2,
                )
                if group["completed_orders"] else 0
            )
            group["repeat_customer_rate"] = _to_percentage(
                group["repeat_customers"],
                group["customers_with_sales"],
            )

            results.append(group)

        return sorted(
            results,
            key=lambda item: item["gross_revenue_cents"],
            reverse=True,
        )

    monthly_trend = []

    for row in monthly_rows:
        revenue_cents = int(row["gross_revenue_cents"] or 0)

        monthly_trend.append({
            "month": row["month"],
            "completed_orders": int(row["completed_orders"]),
            "unique_customers": int(row["unique_customers"]),
            "gross_revenue_cents": revenue_cents,
            "gross_revenue_dollars": _to_dollars(revenue_cents),
        })

    return {
        "dataset_version_id": dataset_version_id,
        "period": {
            "start_date": str(start_date) if start_date else None,
            "end_date": str(end_date) if end_date else None,
        },
        "summary": {
            "total_customers": customer_count,
            "customers_with_sales": customers_with_sales,
            "customers_without_sales": (
                customer_count - customers_with_sales
            ),
            "repeat_customers": repeat_customers,
            "one_time_customers": one_time_customers,
            "completed_orders": total_orders,
            "gross_revenue_cents": total_revenue_cents,
            "gross_revenue_dollars": _to_dollars(
                total_revenue_cents
            ),
            "average_order_value_cents": (
                round(total_revenue_cents / total_orders, 2)
                if total_orders else 0
            ),
            "average_order_value_dollars": (
                round(total_revenue_cents / total_orders / 100, 2)
                if total_orders else 0
            ),
            "customer_purchase_rate": _to_percentage(
                customers_with_sales,
                customer_count,
            ),
            "repeat_customer_rate": _to_percentage(
                repeat_customers,
                customers_with_sales,
            ),
        },
        "by_segment": aggregate_by("segment_name"),
        "by_customer_type": aggregate_by("customer_type"),
        "by_region": aggregate_by("region_name"),
        "monthly_trend": monthly_trend,
        "customers": customer_rows,
    }

