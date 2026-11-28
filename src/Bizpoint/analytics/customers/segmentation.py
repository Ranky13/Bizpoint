from datetime import date
from typing import Any

from Bizpoint.analytics.common.query import execute_query


def _validate_period(
    start_date: date | None,
    end_date: date | None,
) -> None:
    if start_date and end_date and start_date > end_date:
        raise ValueError("start_date cannot be later than end_date")


def _classify_customer(
    recency: int,
    frequency: int,
    monetary: int,
) -> str:
    """
    Assign an RFM segment using the customer's three scores.
    """

    if recency <= 2 and frequency >= 4 and monetary >= 4:
        return "Can't Lose Them"

    if recency >= 4 and frequency >= 4 and monetary >= 4:
        return "Champions"

    if frequency >= 4 and monetary >= 3:
        return "Loyal Customers"

    if recency >= 4 and frequency >= 2:
        return "Potential Loyalists"

    if recency >= 4 and frequency == 1:
        return "New Customers"

    if recency <= 2 and frequency >= 3:
        return "At Risk"

    if recency <= 2 and frequency <= 2:
        return "Hibernating"

    return "Needs Attention"


def get_customer_segmentation(
    dataset_version_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """
    Perform RFM customer segmentation.

    Recency:
        Days since the most recent completed order.

    Frequency:
        Number of completed orders.

    Monetary:
        Gross value of completed orders before returns.

    RFM scores range from 1 to 5.
    Higher scores indicate better purchasing behaviour.
    """

    if not dataset_version_id:
        raise ValueError("dataset_version_id is required")

    _validate_period(start_date, end_date)

    parameters = {
        "dataset_version_id": dataset_version_id,
        "start_date": start_date,
        "end_date": end_date,
    }

    query = """
        WITH eligible_orders AS (
            SELECT
                so.customer_id,
                so.order_date,
                so.total_amount_cents
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
        ),

        analysis_reference AS (
            SELECT
                COALESCE(
                    CAST(:end_date AS DATE),
                    MAX(order_date)::DATE
                ) AS analysis_date
            FROM eligible_orders
        ),

        customer_metrics AS (
            SELECT
                customer_id,
                COUNT(*) AS frequency,
                SUM(total_amount_cents) AS monetary_cents,
                MAX(order_date)::DATE AS last_order_date
            FROM eligible_orders
            GROUP BY customer_id
        ),

        customer_scores AS (
            SELECT
                cm.customer_id,
                cm.frequency,
                cm.monetary_cents,
                cm.last_order_date,
                ar.analysis_date,
                (
                    ar.analysis_date - cm.last_order_date
                )::INTEGER AS recency_days,

                NTILE(5) OVER (
                    ORDER BY
                        (
                            ar.analysis_date - cm.last_order_date
                        ) DESC
                ) AS recency_score,

                NTILE(5) OVER (
                    ORDER BY cm.frequency ASC
                ) AS frequency_score,

                NTILE(5) OVER (
                    ORDER BY cm.monetary_cents ASC
                ) AS monetary_score

            FROM customer_metrics cm
            CROSS JOIN analysis_reference ar
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
            c.segment_id,
            cs.segment_name,
            r.region_name,

            ar.analysis_date,
            sc.last_order_date,
            sc.recency_days,
            COALESCE(sc.frequency, 0) AS frequency,
            COALESCE(sc.monetary_cents, 0) AS monetary_cents,
            sc.recency_score,
            sc.frequency_score,
            sc.monetary_score

        FROM customers c

        CROSS JOIN analysis_reference ar

        LEFT JOIN customer_scores sc
            ON sc.customer_id = c.id

        LEFT JOIN customer_segments cs
            ON cs.id = c.segment_id
           AND cs.dataset_version_id = c.dataset_version_id

        LEFT JOIN regions r
            ON r.id = c.region_id
           AND r.dataset_version_id = c.dataset_version_id

        WHERE c.dataset_version_id = :dataset_version_id

        ORDER BY
            COALESCE(sc.monetary_cents, 0) DESC,
            c.customer_code
    """

    rows = execute_query(query, parameters)

    customers = []

    for row in rows:
        monetary_cents = int(row["monetary_cents"] or 0)
        frequency = int(row["frequency"] or 0)

        if frequency == 0:
            segment = "Not Yet Purchased"
            rfm_score = None
        else:
            recency_score = int(row["recency_score"])
            frequency_score = int(row["frequency_score"])
            monetary_score = int(row["monetary_score"])

            segment = _classify_customer(
                recency_score,
                frequency_score,
                monetary_score,
            )

            rfm_score = (
                recency_score * 100
                + frequency_score * 10
                + monetary_score
            )

        customers.append({
            **row,
            "frequency": frequency,
            "monetary_cents": monetary_cents,
            "monetary_dollars": round(monetary_cents / 100, 2),
            "recency_score": (
                int(row["recency_score"])
                if row["recency_score"] is not None
                else None
            ),
            "frequency_score": (
                int(row["frequency_score"])
                if row["frequency_score"] is not None
                else None
            ),
            "monetary_score": (
                int(row["monetary_score"])
                if row["monetary_score"] is not None
                else None
            ),
            "rfm_score": rfm_score,
            "rfm_segment": segment,
        })

    segment_groups: dict[str, dict[str, Any]] = {}

    for customer in customers:
        segment = customer["rfm_segment"]

        if segment not in segment_groups:
            segment_groups[segment] = {
                "segment": segment,
                "customer_count": 0,
                "completed_orders": 0,
                "monetary_cents": 0,
                "customers_with_sales": 0,
            }

        group = segment_groups[segment]

        group["customer_count"] += 1
        group["completed_orders"] += customer["frequency"]
        group["monetary_cents"] += customer["monetary_cents"]

        if customer["frequency"] > 0:
            group["customers_with_sales"] += 1

    by_segment = []

    for group in segment_groups.values():
        monetary_cents = group["monetary_cents"]

        by_segment.append({
            **group,
            "monetary_dollars": round(monetary_cents / 100, 2),
            "average_revenue_per_customer": round(
                monetary_cents / group["customer_count"] / 100,
                2,
            ),
            "revenue_contribution_percentage": round(
                monetary_cents
                / sum(
                    item["monetary_cents"]
                    for item in segment_groups.values()
                )
                * 100,
                2,
            ) if monetary_cents or any(
                item["monetary_cents"]
                for item in segment_groups.values()
            ) else 0.0,
        })

    by_segment.sort(
        key=lambda item: item["monetary_cents"],
        reverse=True,
    )

    customers_with_sales = sum(
        customer["frequency"] > 0
        for customer in customers
    )

    customers_without_sales = len(customers) - customers_with_sales

    return {
        "dataset_version_id": dataset_version_id,
        "period": {
            "start_date": str(start_date) if start_date else None,
            "end_date": str(end_date) if end_date else None,
        },
        "analysis_date": (
            customers[0]["analysis_date"] if customers else None
        ),
        "summary": {
            "total_customers": len(customers),
            "customers_with_sales": customers_with_sales,
            "customers_without_sales": customers_without_sales,
            "rfm_segment_count": len(by_segment),
            "total_completed_orders": sum(
                customer["frequency"] for customer in customers
            ),
            "total_monetary_cents": sum(
                customer["monetary_cents"] for customer in customers
            ),
            "total_monetary_dollars": round(
                sum(
                    customer["monetary_cents"]
                    for customer in customers
                ) / 100,
                2,
            ),
        },
        "by_segment": by_segment,
        "customers": customers,
    }

