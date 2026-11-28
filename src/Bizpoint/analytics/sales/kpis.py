from datetime import date
from typing import Any

from Bizpoint.analytics.sales.performance import get_sales_performance
from Bizpoint.analytics.sales.products import get_product_performance
from Bizpoint.analytics.sales.segments import get_sales_segments
from Bizpoint.analytics.sales.payments import get_payment_performance
from Bizpoint.analytics.sales.returns import get_returns_performance


def get_sales_kpis(
    dataset_version_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """
    Consolidate sales, product, segment, payment and return analytics.

    This service orchestrates existing analytics services.
    It does not duplicate their underlying SQL calculations.
    """

    if not dataset_version_id:
        raise ValueError("dataset_version_id is required.")

    if start_date and end_date and start_date > end_date:
        raise ValueError("start_date cannot be later than end_date.")

    sales = get_sales_performance(
        dataset_version_id,
        start_date,
        end_date,
    )

    products = get_product_performance(
        dataset_version_id,
        start_date,
        end_date,
    )

    segments = get_sales_segments(
        dataset_version_id,
        start_date,
        end_date,
    )

    payments = get_payment_performance(
        dataset_version_id,
        start_date,
        end_date,
    )

    returns = get_returns_performance(
        dataset_version_id,
        start_date,
        end_date,
    )

    sales_summary = sales["summary"]
    product_summary = products["summary"]
    payment_summary = payments["summary"]
    return_summary = returns["returns"]["summary"]
    refund_summary = returns["refunds"]["summary"]

    kpis = {
        "completed_orders": sales_summary["completed_orders"],
        "unique_customers": sales_summary["unique_customers"],
        "gross_revenue": sales_summary["gross_revenue_dollars"],
        "average_order_value": sales_summary["average_order_value_dollars"],

        "products_sold": product_summary["products_with_sales"],
        "units_sold": product_summary["units_sold"],
        "gross_product_sales": product_summary["gross_sales_cents_dollars"],
        "discounts": product_summary["discount_amount_cents_dollars"],
        "net_product_sales": product_summary["net_sales_cents_dollars"],

        "payment_attempts": payment_summary["payment_attempts"],
        "successful_payments": payment_summary["successful_payments"],
        "payment_success_rate": payment_summary["success_rate_percentage"],
        "successful_collections": payment_summary[
            "successful_collections_cents_dollars"
        ],

        "return_attempts": return_summary["return_attempts"],
        "completed_returns": return_summary["completed_returns"],
        "requested_returns": return_summary["requested_returns"],
        "approved_returns": return_summary["approved_returns"],
        "rejected_returns": return_summary["rejected_returns"],
        "returned_units": return_summary["returned_units"],
        "return_value": return_summary["completed_return_value_dollars"],

        "refund_attempts": refund_summary["refund_attempts"],
        "successful_refunds": refund_summary["successful_refunds"],
        "refund_success_rate": refund_summary[
            "refund_success_rate_percentage"
        ],
        "successful_refund_value": refund_summary[
            "successful_refund_amount_dollars"
        ],
    }

    reconciliation = {
        "sales_match_product_net_sales": (
            sales_summary["gross_revenue_cents"]
            == product_summary["net_sales_cents"]
        ),

        "sales_returns_match_product_returns": (
            return_summary["completed_return_value_cents"]
            == product_summary["returned_amount_cents"]
        ),

        "successful_collections_match_payment_summary": (
            payment_summary["successful_collections_cents"]
            == sum(
                row["successful_collections_cents"]
                for row in payments["by_method"]
            )
        ),

        "refunds_match_refund_status_breakdown": (
            refund_summary["successful_refund_amount_cents"]
            == sum(
                row["amount_cents"]
                for row in returns["refunds"]["by_status"]
                if row["status"] == "successful"
            )
        ),

        "return_status_counts_reconcile": (
            return_summary["return_attempts"]
            == (
                return_summary["completed_returns"]
                + return_summary["requested_returns"]
                + return_summary["approved_returns"]
                + return_summary["pending_returns"]
                + return_summary["rejected_returns"]
                + return_summary["cancelled_returns"]
            )
        ),
    }

    reconciliation["all_checks_passed"] = all(
        reconciliation.values()
    )

    return {
        "dataset_version_id": dataset_version_id,
        "currency": "USD",
        "period": {
            "start_date": start_date,
            "end_date": end_date,
        },
        "kpis": kpis,
        "sales_performance": sales,
        "product_performance": products,
        "sales_segments": segments,
        "payment_performance": payments,
        "returns_performance": returns,
        "reconciliation": reconciliation,
    }
