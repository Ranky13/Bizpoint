from datetime import date
from typing import Any

from Bizpoint.analytics.common.query import execute_query


def get_revenue_metrics(
    dataset_version_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:

    if not dataset_version_id:
        raise ValueError("dataset_version_id is required.")

    if start_date and end_date and start_date > end_date:
        raise ValueError("start_date cannot be later than end_date.")

    parameters = {
        "dataset_version_id": dataset_version_id,
        "start_date": start_date,
        "end_date": end_date,
    }

    sales_query = """
        SELECT
            COALESCE(SUM(total_amount_cents), 0) AS gross_revenue_cents,
            COUNT(*) AS completed_orders
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
    """

    returns_query = """
        SELECT
            COALESCE(SUM(sri.return_amount_cents), 0)
                AS sales_returns_cents,
            COUNT(DISTINCT sr.id) AS completed_returns
        FROM sales_returns AS sr
        INNER JOIN sales_return_items AS sri
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
              OR sr.return_date < CAST(:end_date AS DATE) + INTERVAL '1 day'
          )
    """

    sales = execute_query(sales_query, parameters)[0]
    returns = execute_query(returns_query, parameters)[0]

    gross_revenue_cents = int(sales["gross_revenue_cents"])
    sales_returns_cents = int(returns["sales_returns_cents"])
    net_revenue_cents = gross_revenue_cents - sales_returns_cents

    return {
        "dataset_version_id": dataset_version_id,
        "period": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },
        "completed_orders": int(sales["completed_orders"]),
        "completed_returns": int(returns["completed_returns"]),
        "gross_revenue_cents": gross_revenue_cents,
        "sales_returns_cents": sales_returns_cents,
        "net_revenue_cents": net_revenue_cents,
        "gross_revenue": round(gross_revenue_cents / 100, 2),
        "sales_returns": round(sales_returns_cents / 100, 2),
        "net_revenue": round(net_revenue_cents / 100, 2),
        "currency": "USD",
    }
