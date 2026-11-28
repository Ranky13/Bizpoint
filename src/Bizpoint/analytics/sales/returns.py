from datetime import date
from typing import Any

from Bizpoint.analytics.common.query import execute_query


def get_returns_performance(
    dataset_version_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """
    Analyse sales returns and customer refund settlements.

    Returns are recognised by return_date.
    Refunds are analysed separately by refund_date.
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

    return_summary_query = """
        SELECT
            COUNT(DISTINCT sr.id) AS return_attempts,

            COUNT(DISTINCT sr.id) FILTER (
                WHERE sr.status = 'completed'
            ) AS completed_returns,

            COUNT(DISTINCT sr.id) FILTER (
                WHERE sr.status = 'requested'
            ) AS requested_returns,

            COUNT(DISTINCT sr.id) FILTER (
                WHERE sr.status = 'approved'
            ) AS approved_returns,

            COUNT(DISTINCT sr.id) FILTER (
                WHERE sr.status = 'pending'
            ) AS pending_returns,

            COUNT(DISTINCT sr.id) FILTER (
                WHERE sr.status = 'rejected'
            ) AS rejected_returns,

            COUNT(DISTINCT sr.id) FILTER (
                WHERE sr.status = 'cancelled'
            ) AS cancelled_returns,

            COALESCE(
                SUM(sri.quantity) FILTER (
                    WHERE sr.status = 'completed'
                ),
                0
            ) AS returned_units,

            COALESCE(
                SUM(sri.return_amount_cents) FILTER (
                    WHERE sr.status = 'completed'
                ),
                0
            ) AS completed_return_value_cents

        FROM sales_returns sr

        LEFT JOIN sales_return_items sri
            ON sri.return_id = sr.id
           AND sri.dataset_version_id = sr.dataset_version_id

        WHERE sr.dataset_version_id = :dataset_version_id
          AND (
              CAST(:start_date AS DATE) IS NULL
              OR sr.return_date >= CAST(:start_date AS DATE)
          )
          AND (
              CAST(:end_date AS DATE) IS NULL
              OR sr.return_date < CAST(:end_date AS DATE)
                  + INTERVAL '1 day'
          );
    """

    return_summary = execute_query(
        return_summary_query,
        parameters,
    )[0]

    return_summary["completed_return_value_dollars"] = round(
        return_summary["completed_return_value_cents"] / 100,
        2,
    )

    reason_query = """
        SELECT
            COALESCE(sr.reason, 'Unspecified') AS return_reason,
            COUNT(DISTINCT sr.id) AS completed_returns,
            COALESCE(SUM(sri.quantity), 0) AS returned_units,
            COALESCE(
                SUM(sri.return_amount_cents),
                0
            ) AS return_value_cents

        FROM sales_returns sr

        LEFT JOIN sales_return_items sri
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

        GROUP BY sr.reason
        ORDER BY return_value_cents DESC;
    """

    by_reason = execute_query(
        reason_query,
        parameters,
    )

    for row in by_reason:
        row["return_value_dollars"] = round(
            row["return_value_cents"] / 100,
            2,
        )

    monthly_query = """
        SELECT
            DATE_TRUNC('month', sr.return_date)::date AS month,

            COUNT(DISTINCT sr.id) FILTER (
                WHERE sr.status = 'completed'
            ) AS completed_returns,

            COUNT(DISTINCT sr.id) FILTER (
                WHERE sr.status <> 'completed'
            ) AS other_return_attempts,

            COALESCE(
                SUM(sri.quantity) FILTER (
                    WHERE sr.status = 'completed'
                ),
                0
            ) AS returned_units,

            COALESCE(
                SUM(sri.return_amount_cents) FILTER (
                    WHERE sr.status = 'completed'
                ),
                0
            ) AS return_value_cents

        FROM sales_returns sr

        LEFT JOIN sales_return_items sri
            ON sri.return_id = sr.id
           AND sri.dataset_version_id = sr.dataset_version_id

        WHERE sr.dataset_version_id = :dataset_version_id
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
        ORDER BY month;
    """

    monthly_trend = execute_query(
        monthly_query,
        parameters,
    )

    for row in monthly_trend:
        row["return_value_dollars"] = round(
            row["return_value_cents"] / 100,
            2,
        )

    refund_summary_query = """
        SELECT
            COUNT(*) AS refund_attempts,

            COUNT(*) FILTER (
                WHERE status = 'successful'
            ) AS successful_refunds,

            COUNT(*) FILTER (
                WHERE status = 'pending'
            ) AS pending_refunds,

            COUNT(*) FILTER (
                WHERE status = 'failed'
            ) AS failed_refunds,

            COUNT(*) FILTER (
                WHERE status = 'reversed'
            ) AS reversed_refunds,

            COALESCE(
                SUM(amount_cents) FILTER (
                    WHERE status = 'successful'
                ),
                0
            ) AS successful_refund_amount_cents,

            COALESCE(
                SUM(amount_cents) FILTER (
                    WHERE status = 'pending'
                ),
                0
            ) AS pending_refund_amount_cents

        FROM sales_refunds

        WHERE dataset_version_id = :dataset_version_id
          AND (
              CAST(:start_date AS DATE) IS NULL
              OR refund_date >= CAST(:start_date AS DATE)
          )
          AND (
              CAST(:end_date AS DATE) IS NULL
              OR refund_date < CAST(:end_date AS DATE)
                  + INTERVAL '1 day'
          );
    """

    refund_summary = execute_query(
        refund_summary_query,
        parameters,
    )[0]

    refund_summary["refund_success_rate_percentage"] = (
        round(
            refund_summary["successful_refunds"]
            / refund_summary["refund_attempts"] * 100,
            2,
        )
        if refund_summary["refund_attempts"] > 0
        else 0.0
    )

    refund_summary["successful_refund_amount_dollars"] = round(
        refund_summary["successful_refund_amount_cents"] / 100,
        2,
    )

    refund_summary["pending_refund_amount_dollars"] = round(
        refund_summary["pending_refund_amount_cents"] / 100,
        2,
    )

    refund_status_query = """
        SELECT
            status,
            COUNT(*) AS refund_count,
            COALESCE(SUM(amount_cents), 0) AS amount_cents

        FROM sales_refunds

        WHERE dataset_version_id = :dataset_version_id
          AND (
              CAST(:start_date AS DATE) IS NULL
              OR refund_date >= CAST(:start_date AS DATE)
          )
          AND (
              CAST(:end_date AS DATE) IS NULL
              OR refund_date < CAST(:end_date AS DATE)
                  + INTERVAL '1 day'
          )

        GROUP BY status
        ORDER BY refund_count DESC;
    """

    refunds_by_status = execute_query(
        refund_status_query,
        parameters,
    )

    for row in refunds_by_status:
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
        "returns": {
            "summary": return_summary,
            "by_reason": by_reason,
            "monthly_trend": monthly_trend,
        },
        "refunds": {
            "summary": refund_summary,
            "by_status": refunds_by_status,
        },
    }


