from datetime import date
from typing import Any

from Bizpoint.analytics.customers.performance import (
    get_customer_performance,
)
from Bizpoint.analytics.customers.segmentation import (
    get_customer_segmentation,
)
from Bizpoint.analytics.customers.retention import (
    get_customer_retention,
)
from Bizpoint.analytics.customers.lifetime_value import (
    get_customer_lifetime_value,
)


def get_customer_kpis(
    dataset_version_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """
    Consolidate customer performance, RFM segmentation,
    retention and historical lifetime value analytics.
    """

    if not dataset_version_id:
        raise ValueError("dataset_version_id is required")

    if start_date and end_date and start_date > end_date:
        raise ValueError("start_date cannot be later than end_date")

    performance = get_customer_performance(
        dataset_version_id,
        start_date,
        end_date,
    )

    segmentation = get_customer_segmentation(
        dataset_version_id,
        start_date,
        end_date,
    )

    retention = get_customer_retention(
        dataset_version_id,
        start_date,
        end_date,
    )

    # Historical CLV is intentionally calculated across the
    # full dataset, not restricted to the reporting period.
    lifetime_value = get_customer_lifetime_value(
        dataset_version_id,
    )

    p = performance["summary"]
    s = segmentation["summary"]
    r = retention["summary"]
    l = lifetime_value["summary"]

    reconciliation = {
        "customer_counts_match": (
            p["total_customers"] == l["total_customers"]
        ),
        "purchasing_customer_counts_match": (
            p["customers_with_sales"] == l["purchasing_customers"]
        ),
        "completed_orders_match": (
            p["completed_orders"] == l["completed_orders"]
        ),
        "gross_revenue_matches": (
            p["gross_revenue_cents"] == l["gross_revenue_cents"]
        ),
        "rfm_monetary_matches_gross_revenue": (
            s["total_monetary_cents"] == l["gross_revenue_cents"]
        ),
        "first_time_buyers_match_purchasing_customers": (
            r["first_time_buyers"] == l["purchasing_customers"]
        ),
        "net_lifetime_revenue_reconciles": (
            l["gross_revenue_cents"]
            - l["returned_amount_cents"]
            == l["net_lifetime_revenue_cents"]
        ),
    }

    reconciliation["all_checks_passed"] = all(
        reconciliation.values()
    )

    return {
        "dataset_version_id": dataset_version_id,
        "period": performance["period"],
        "kpis": {
            "total_customers": p["total_customers"],
            "customers_with_sales": p["customers_with_sales"],
            "customers_without_sales": p["customers_without_sales"],
            "customer_purchase_rate": p["customer_purchase_rate"],
            "repeat_customers": p["repeat_customers"],
            "repeat_customer_rate": p["repeat_customer_rate"],
            "completed_orders": p["completed_orders"],
            "gross_revenue": l["gross_revenue_dollars"],
            "sales_returns": l["returned_amount_dollars"],
            "net_lifetime_revenue": (
                l["net_lifetime_revenue_dollars"]
            ),
            "average_order_value": p["average_order_value_dollars"],
            "average_clv_per_purchasing_customer": (
                l["average_clv_per_purchasing_customer"]
            ),
            "average_clv_per_registered_customer": (
                l["average_clv_per_registered_customer"]
            ),
            "first_time_buyers": r["first_time_buyers"],
            "returning_customer_months": (
                r["returning_customer_months"]
            ),
            "monthly_repeat_customer_rate": (
                r["overall_repeat_customer_rate"]
            ),
            "rfm_segment_count": s["rfm_segment_count"],
            "cohort_count": r["cohort_count"],
        },
        "performance": performance,
        "segmentation": segmentation,
        "retention": retention,
        "lifetime_value": lifetime_value,
        "reconciliation": reconciliation,
    }
