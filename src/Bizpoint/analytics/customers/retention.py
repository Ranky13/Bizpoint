from datetime import date
from typing import Any

from Bizpoint.analytics.common.query import execute_query


def _validate_period(
    start_date: date | None,
    end_date: date | None,
) -> None:
    if start_date and end_date and start_date > end_date:
        raise ValueError("start_date cannot be later than end_date")


def _percentage(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0

    return round(numerator / denominator * 100, 2)


def get_customer_retention(
    dataset_version_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """
    Analyse customer acquisition, repeat purchasing and cohort retention.

    Acquisition:
        Based on customer registration_date.

    First-time buyers:
        Based on each customer's first-ever completed order.

    Returning customers:
        Customers with a previous completed order who purchase again
        during the reporting month.

    Cohort retention:
        Customers grouped by their first-ever completed purchase month,
        then tracked across subsequent calendar months.

    All sales activity uses completed orders only.
    """

    if not dataset_version_id:
        raise ValueError("dataset_version_id is required")

    _validate_period(start_date, end_date)

    parameters = {
        "dataset_version_id": dataset_version_id,
        "start_date": start_date,
        "end_date": end_date,
    }

    monthly_query = """
        WITH first_purchase AS (
            SELECT
                customer_id,
                MIN(order_date) AS first_order_date
            FROM sales_orders
            WHERE dataset_version_id = :dataset_version_id
              AND status = 'completed'
            GROUP BY customer_id
        ),

        monthly_orders AS (
            SELECT
                so.customer_id,
                DATE_TRUNC('month', so.order_date)::DATE AS month,
                COUNT(so.id) AS completed_orders,
                SUM(so.total_amount_cents) AS revenue_cents
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
            GROUP BY
                so.customer_id,
                DATE_TRUNC('month', so.order_date)
        ),

        monthly_customer_activity AS (
            SELECT
                mo.month,
                COUNT(DISTINCT mo.customer_id) AS active_customers,
                COUNT(DISTINCT mo.customer_id) FILTER (
                    WHERE DATE_TRUNC(
                        'month',
                        fp.first_order_date
                    ) = mo.month
                ) AS first_time_buyers,
                COUNT(DISTINCT mo.customer_id) FILTER (
                    WHERE DATE_TRUNC(
                        'month',
                        fp.first_order_date
                    ) < mo.month
                ) AS returning_customers,
                SUM(mo.completed_orders) AS completed_orders,
                SUM(mo.revenue_cents) AS revenue_cents
            FROM monthly_orders mo
            JOIN first_purchase fp
                ON fp.customer_id = mo.customer_id
            GROUP BY mo.month
        ),

        monthly_registrations AS (
            SELECT
                DATE_TRUNC(
                    'month',
                    c.registration_date
                )::DATE AS month,
                COUNT(c.id) AS new_registrations
            FROM customers c
            WHERE c.dataset_version_id = :dataset_version_id
              AND (
                    CAST(:start_date AS DATE) IS NULL
                    OR c.registration_date >= CAST(:start_date AS DATE)
                  )
              AND (
                    CAST(:end_date AS DATE) IS NULL
                    OR c.registration_date <= CAST(:end_date AS DATE)
                  )
            GROUP BY DATE_TRUNC('month', c.registration_date)
        )

        SELECT
            COALESCE(
                a.month,
                r.month
            ) AS month,
            COALESCE(r.new_registrations, 0) AS new_registrations,
            COALESCE(a.first_time_buyers, 0) AS first_time_buyers,
            COALESCE(a.returning_customers, 0) AS returning_customers,
            COALESCE(a.active_customers, 0) AS active_customers,
            COALESCE(a.completed_orders, 0) AS completed_orders,
            COALESCE(a.revenue_cents, 0) AS revenue_cents

        FROM monthly_customer_activity a

        FULL OUTER JOIN monthly_registrations r
            ON r.month = a.month

        ORDER BY month
    """

    monthly_rows = execute_query(monthly_query, parameters)

    cohort_query = """
        WITH first_purchase AS (
            SELECT
                customer_id,
                MIN(order_date)::DATE AS first_order_date
            FROM sales_orders
            WHERE dataset_version_id = :dataset_version_id
              AND status = 'completed'
              AND (
                    CAST(:end_date AS DATE) IS NULL
                    OR order_date < CAST(:end_date AS DATE)
                        + INTERVAL '1 day'
                  )
            GROUP BY customer_id
        ),

        cohort_customers AS (
            SELECT
                customer_id,
                DATE_TRUNC(
                    'month',
                    first_order_date
                )::DATE AS cohort_month
            FROM first_purchase
            WHERE (
                    CAST(:start_date AS DATE) IS NULL
                    OR first_order_date >= CAST(:start_date AS DATE)
                  )
        ),

        cohort_sizes AS (
            SELECT
                cohort_month,
                COUNT(DISTINCT customer_id) AS cohort_size
            FROM cohort_customers
            GROUP BY cohort_month
        ),

        reference_date AS (
            SELECT
                COALESCE(
                    CAST(:end_date AS DATE),
                    MAX(first_order_date)
                )::DATE AS analysis_date
            FROM first_purchase
        ),

        cohort_periods AS (
            SELECT
                cs.cohort_month,
                cs.cohort_size,
                gs.month_number
            FROM cohort_sizes cs
            CROSS JOIN reference_date rd
            CROSS JOIN LATERAL GENERATE_SERIES(
                0,
                GREATEST(
                    0,
                    (
                        EXTRACT(YEAR FROM AGE(
                            DATE_TRUNC('month', rd.analysis_date),
                            cs.cohort_month
                        )) * 12
                        +
                        EXTRACT(MONTH FROM AGE(
                            DATE_TRUNC('month', rd.analysis_date),
                            cs.cohort_month
                        ))
                    )::INTEGER
                )
            ) AS gs(month_number)
        ),

        monthly_activity AS (
            SELECT DISTINCT
                cc.cohort_month,
                DATE_TRUNC(
                    'month',
                    so.order_date
                )::DATE AS activity_month,
                so.customer_id
            FROM cohort_customers cc
            JOIN sales_orders so
                ON so.customer_id = cc.customer_id
               AND so.dataset_version_id = :dataset_version_id
               AND so.status = 'completed'
               AND so.order_date >= cc.cohort_month
               AND (
                    CAST(:end_date AS DATE) IS NULL
                    OR so.order_date < CAST(:end_date AS DATE)
                        + INTERVAL '1 day'
               )
        )

        SELECT
            cp.cohort_month,
            cp.month_number,
            cp.cohort_size,
            COUNT(DISTINCT ma.customer_id) AS retained_customers,
            ROUND(
                COUNT(DISTINCT ma.customer_id)::NUMERIC
                / NULLIF(cp.cohort_size, 0) * 100,
                2
            ) AS retention_percentage

        FROM cohort_periods cp

        LEFT JOIN monthly_activity ma
            ON ma.cohort_month = cp.cohort_month
           AND ma.activity_month = (
                cp.cohort_month
                + (cp.month_number * INTERVAL '1 month')
           )::DATE

        GROUP BY
            cp.cohort_month,
            cp.month_number,
            cp.cohort_size

        ORDER BY
            cp.cohort_month,
            cp.month_number
    """

    cohort_rows = execute_query(cohort_query, parameters)

    monthly_trend = []

    for row in monthly_rows:
        active = int(row["active_customers"])
        returning = int(row["returning_customers"])
        revenue_cents = int(row["revenue_cents"] or 0)

        monthly_trend.append({
            "month": row["month"],
            "new_registrations": int(row["new_registrations"]),
            "first_time_buyers": int(row["first_time_buyers"]),
            "returning_customers": returning,
            "active_customers": active,
            "completed_orders": int(row["completed_orders"]),
            "revenue_cents": revenue_cents,
            "revenue_dollars": round(revenue_cents / 100, 2),
            "repeat_customer_rate": _percentage(
                returning,
                active,
            ),
        })

    cohort_retention = [
        {
            "cohort_month": row["cohort_month"],
            "month_number": int(row["month_number"]),
            "cohort_size": int(row["cohort_size"]),
            "retained_customers": int(row["retained_customers"]),
            "retention_percentage": float(
                row["retention_percentage"] or 0
            ),
        }
        for row in cohort_rows
    ]

    cohort_summaries = {}

    for row in cohort_retention:
        month = row["cohort_month"]

        if month not in cohort_summaries:
            cohort_summaries[month] = {
                "cohort_month": month,
                "cohort_size": row["cohort_size"],
                "monthly_retention": {},
            }

        cohort_summaries[month]["monthly_retention"][
            row["month_number"]
        ] = {
            "retained_customers": row["retained_customers"],
            "retention_percentage": row["retention_percentage"],
        }

    total_registrations = sum(
        row["new_registrations"] for row in monthly_trend
    )

    total_first_time_buyers = sum(
        row["first_time_buyers"] for row in monthly_trend
    )

    total_returning_customer_months = sum(
        row["returning_customers"] for row in monthly_trend
    )

    total_active_customer_months = sum(
        row["active_customers"] for row in monthly_trend
    )

    return {
        "dataset_version_id": dataset_version_id,
        "period": {
            "start_date": str(start_date) if start_date else None,
            "end_date": str(end_date) if end_date else None,
        },
        "summary": {
            "new_registrations": total_registrations,
            "first_time_buyers": total_first_time_buyers,
            "returning_customer_months": (
                total_returning_customer_months
            ),
            "active_customer_months": total_active_customer_months,
            "overall_repeat_customer_rate": _percentage(
                total_returning_customer_months,
                total_active_customer_months,
            ),
            "cohort_count": len(cohort_summaries),
        },
        "monthly_trend": monthly_trend,
        "cohort_retention": cohort_retention,
        "cohort_summaries": list(cohort_summaries.values()),
    }
