from datetime import date
from typing import Any

from Bizpoint.analytics.common.query import execute_query
from Bizpoint.analytics.financial.revenue import get_revenue_metrics


def _validate_period(
    start_date: date | None,
    end_date: date | None,
) -> None:
    if start_date and end_date and start_date > end_date:
        raise ValueError("start_date cannot be later than end_date.")


def _add_dollar_values(
    rows: list[dict[str, Any]],
    amount_fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    for row in rows:
        for field in amount_fields:
            if field in row and row[field] is not None:
                row[f"{field}_dollars"] = round(
                    row[field] / 100,
                    2,
                )

    return rows


def get_sales_performance(
    dataset_version_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """
    Return sales performance metrics and breakdowns.

    Revenue is based on completed sales orders.
    Returns are recognized on their completion date.
    Store performance uses the sales-origin store.
    """

    if not dataset_version_id:
        raise ValueError("dataset_version_id is required.")

    _validate_period(start_date, end_date)

    parameters = {
        "dataset_version_id": dataset_version_id,
        "start_date": start_date,
        "end_date": end_date,
    }

    # Reuse the existing revenue service as the authoritative
    # source for gross revenue, returns and net revenue.
    revenue = get_revenue_metrics(
        dataset_version_id=dataset_version_id,
        start_date=start_date,
        end_date=end_date,
    )

    # Overall order metrics.
    summary_query = """
        SELECT
            COUNT(*) AS completed_orders,
            COALESCE(SUM(total_amount_cents), 0) AS gross_revenue_cents,
            COALESCE(AVG(total_amount_cents), 0) AS average_order_value_cents,
            COUNT(DISTINCT customer_id) AS unique_customers
        FROM sales_orders
        WHERE dataset_version_id = :dataset_version_id
          AND status = 'completed'
          AND (
              CAST(:start_date AS DATE) IS NULL
              OR order_date >= CAST(:start_date AS DATE)
          )
          AND (
              CAST(:end_date AS DATE) IS NULL
              OR order_date < CAST(:end_date AS DATE) + INTERVAL '1 day'
          );
    """

    summary_rows = execute_query(summary_query, parameters)
    summary = summary_rows[0]

    # Monthly completed sales.
    monthly_query = """
        WITH monthly_sales AS (
            SELECT
                DATE_TRUNC('month', order_date)::DATE AS month,
                COUNT(*) AS completed_orders,
                COALESCE(SUM(total_amount_cents), 0)
                    AS gross_revenue_cents
            FROM sales_orders
            WHERE dataset_version_id = :dataset_version_id
              AND status = 'completed'
              AND (
                  CAST(:start_date AS DATE) IS NULL
                  OR order_date >= CAST(:start_date AS DATE)
              )
              AND (
                  CAST(:end_date AS DATE) IS NULL
                  OR order_date < CAST(:end_date AS DATE)
                      + INTERVAL '1 day'
              )
            GROUP BY DATE_TRUNC('month', order_date)
        ),
        monthly_returns AS (
            SELECT
                DATE_TRUNC('month', sr.return_date)::DATE AS month,
                COUNT(DISTINCT sr.id) AS completed_returns,
                COALESCE(SUM(sri.return_amount_cents), 0)
                    AS sales_returns_cents
            FROM sales_returns sr
            JOIN sales_return_items sri
                ON sri.return_id = sr.id
               AND sri.dataset_version_id = sr.dataset_version_id
            WHERE sr.dataset_version_id = :dataset_version_id
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
            GROUP BY DATE_TRUNC('month', sr.return_date)
        )
        SELECT
            COALESCE(s.month, r.month) AS month,
            COALESCE(s.completed_orders, 0) AS completed_orders,
            COALESCE(s.gross_revenue_cents, 0)
                AS gross_revenue_cents,
            COALESCE(r.completed_returns, 0) AS completed_returns,
            COALESCE(r.sales_returns_cents, 0)
                AS sales_returns_cents,
            COALESCE(s.gross_revenue_cents, 0)
                - COALESCE(r.sales_returns_cents, 0)
                AS net_revenue_cents
        FROM monthly_sales s
        FULL OUTER JOIN monthly_returns r
            ON s.month = r.month
        ORDER BY month;
    """

    monthly_trend = execute_query(monthly_query, parameters)

    # Performance by sales channel.
    channel_query = """
        SELECT
            COALESCE(NULLIF(TRIM(sales_channel), ''), 'Unspecified')
                AS sales_channel,
            COUNT(*) AS completed_orders,
            COALESCE(SUM(total_amount_cents), 0)
                AS gross_revenue_cents,
            COALESCE(AVG(total_amount_cents), 0)
                AS average_order_value_cents
        FROM sales_orders
        WHERE dataset_version_id = :dataset_version_id
          AND status = 'completed'
          AND (
              CAST(:start_date AS DATE) IS NULL
              OR order_date >= CAST(:start_date AS DATE)
          )
          AND (
              CAST(:end_date AS DATE) IS NULL
              OR order_date < CAST(:end_date AS DATE) + INTERVAL '1 day'
          )
        GROUP BY COALESCE(
            NULLIF(TRIM(sales_channel), ''),
            'Unspecified'
        )
        ORDER BY gross_revenue_cents DESC;
    """

    by_channel = execute_query(channel_query, parameters)

    # Performance by the store where the sale originated.
    store_query = """
        SELECT
            COALESCE(st.store_name, 'Unassigned') AS store_name,
            COUNT(so.id) AS completed_orders,
            COALESCE(SUM(so.total_amount_cents), 0)
                AS gross_revenue_cents,
            COALESCE(AVG(so.total_amount_cents), 0)
                AS average_order_value_cents
        FROM sales_orders so
        LEFT JOIN stores st
            ON st.id = so.sales_store_id
           AND st.dataset_version_id = so.dataset_version_id
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
        GROUP BY st.store_name
        ORDER BY gross_revenue_cents DESC;
    """

    by_store = execute_query(store_query, parameters)

    # Convert monetary values from cents to dollars.
    summary["gross_revenue_dollars"] = round(
        summary["gross_revenue_cents"] / 100,
        2,
    )
    summary["average_order_value_dollars"] = round(
        summary["average_order_value_cents"] / 100,
        2,
    )

    monthly_trend = _add_dollar_values(
        monthly_trend,
        (
            "gross_revenue_cents",
            "sales_returns_cents",
            "net_revenue_cents",
        ),
    )

    by_channel = _add_dollar_values(
        by_channel,
        (
            "gross_revenue_cents",
            "average_order_value_cents",
        ),
    )

    by_store = _add_dollar_values(
        by_store,
        (
            "gross_revenue_cents",
            "average_order_value_cents",
        ),
    )

    return {
        "dataset_version_id": dataset_version_id,
        "currency": "USD",
        "period": {
            "start_date": start_date,
            "end_date": end_date,
        },
        "summary": summary,
        "revenue": revenue,
        "monthly_trend": monthly_trend,
        "by_channel": by_channel,
        "by_store": by_store,
    }
