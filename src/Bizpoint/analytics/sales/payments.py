from datetime import date
from typing import Any

from Bizpoint.analytics.common.query import execute_query


def get_payment_performance(
    dataset_version_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """
    Analyse sales payment attempts and successful collections.

    Payment attempts are grouped by payment_date.
    Successful payments measure cash collections, not revenue.
    """

    if not dataset_version_id:
        raise ValueError("dataset_version_id is required.")

    if start_date and end_date and start_date > end_date:
        raise ValueError("start_date cannot be later than end_date.")

    parameters = {
        "dataset_version_id": dataset_version_id,
        "start_date": start_date,
        "end_date": end_date,
    }

    summary_query = """
        SELECT
            COUNT(*) AS payment_attempts,

            COUNT(*) FILTER (
                WHERE status = 'successful'
            ) AS successful_payments,

            COUNT(*) FILTER (
                WHERE status = 'pending'
            ) AS pending_payments,

            COUNT(*) FILTER (
                WHERE status = 'failed'
            ) AS failed_payments,

            COUNT(*) FILTER (
                WHERE status = 'reversed'
            ) AS reversed_payments,

            COALESCE(
                SUM(amount_cents) FILTER (
                    WHERE status = 'successful'
                ),
                0
            ) AS successful_collections_cents,

            COALESCE(
                SUM(amount_cents) FILTER (
                    WHERE status = 'pending'
                ),
                0
            ) AS pending_amount_cents,

            COALESCE(
                SUM(amount_cents) FILTER (
                    WHERE status = 'failed'
                ),
                0
            ) AS failed_amount_cents,

            COALESCE(
                SUM(amount_cents) FILTER (
                    WHERE status = 'reversed'
                ),
                0
            ) AS reversed_amount_cents

        FROM sales_payments

        WHERE dataset_version_id = :dataset_version_id
          AND (
              CAST(:start_date AS DATE) IS NULL
              OR payment_date >= CAST(:start_date AS DATE)
          )
          AND (
              CAST(:end_date AS DATE) IS NULL
              OR payment_date < CAST(:end_date AS DATE)
                  + INTERVAL '1 day'
          );
    """

    summary = execute_query(
        summary_query,
        parameters,
    )[0]

    summary["success_rate_percentage"] = (
        round(
            summary["successful_payments"]
            / summary["payment_attempts"] * 100,
            2,
        )
        if summary["payment_attempts"] > 0
        else 0.0
    )

    monetary_fields = (
        "successful_collections_cents",
        "pending_amount_cents",
        "failed_amount_cents",
        "reversed_amount_cents",
    )

    for field in monetary_fields:
        summary[f"{field}_dollars"] = round(
            summary[field] / 100,
            2,
        )

    method_query = """
        SELECT
            COALESCE(pm.method_name, 'Unknown') AS payment_method,

            COUNT(sp.id) AS payment_attempts,

            COUNT(sp.id) FILTER (
                WHERE sp.status = 'successful'
            ) AS successful_payments,

            COUNT(sp.id) FILTER (
                WHERE sp.status = 'pending'
            ) AS pending_payments,

            COUNT(sp.id) FILTER (
                WHERE sp.status = 'failed'
            ) AS failed_payments,

            COUNT(sp.id) FILTER (
                WHERE sp.status = 'reversed'
            ) AS reversed_payments,

            COALESCE(
                SUM(sp.amount_cents) FILTER (
                    WHERE sp.status = 'successful'
                ),
                0
            ) AS successful_collections_cents

        FROM sales_payments sp

        LEFT JOIN payment_methods pm
            ON pm.id = sp.payment_method_id
           AND pm.dataset_version_id = sp.dataset_version_id

        WHERE sp.dataset_version_id = :dataset_version_id
          AND (
              CAST(:start_date AS DATE) IS NULL
              OR sp.payment_date >= CAST(:start_date AS DATE)
          )
          AND (
              CAST(:end_date AS DATE) IS NULL
              OR sp.payment_date < CAST(:end_date AS DATE)
                  + INTERVAL '1 day'
          )

        GROUP BY pm.method_name
        ORDER BY successful_collections_cents DESC;
    """

    by_method = execute_query(
        method_query,
        parameters,
    )

    for row in by_method:
        row["success_rate_percentage"] = (
            round(
                row["successful_payments"]
                / row["payment_attempts"] * 100,
                2,
            )
            if row["payment_attempts"] > 0
            else 0.0
        )

        row["successful_collections_dollars"] = round(
            row["successful_collections_cents"] / 100,
            2,
        )

    status_query = """
        SELECT
            status,
            COUNT(*) AS payment_count,
            COALESCE(SUM(amount_cents), 0) AS amount_cents

        FROM sales_payments

        WHERE dataset_version_id = :dataset_version_id
          AND (
              CAST(:start_date AS DATE) IS NULL
              OR payment_date >= CAST(:start_date AS DATE)
          )
          AND (
              CAST(:end_date AS DATE) IS NULL
              OR payment_date < CAST(:end_date AS DATE)
                  + INTERVAL '1 day'
          )

        GROUP BY status
        ORDER BY payment_count DESC;
    """

    by_status = execute_query(
        status_query,
        parameters,
    )

    for row in by_status:
        row["amount_dollars"] = round(
            row["amount_cents"] / 100,
            2,
        )

    return {
        "dataset_version_id": dataset_version_id,
        "currency": "USD",
        "period": {
            "start_date": start_date,
            "end_date": end_date,
        },
        "summary": summary,
        "by_method": by_method,
        "by_status": by_status,
    }
