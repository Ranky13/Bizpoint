from datetime import date
from typing import Any

from Bizpoint.analytics.common.query import execute_query


def get_cash_flow_metrics(
    dataset_version_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """
    Calculate cash movement from successful payment records.

    Inflow:
        Successful customer payments.

    Outflows:
        Successful customer refunds.
        Successful expense payments.
        Successful supplier payments.

    Cash movements are recognised using their payment dates.
    All monetary calculations use integer cents.
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

    cash_movements_query = """
        SELECT
            DATE_TRUNC('month', payment_date)::DATE AS month,
            'customer_collections' AS movement_type,
            amount_cents,
            'inflow' AS direction
        FROM sales_payments
        WHERE dataset_version_id = :dataset_version_id
          AND status = 'successful'
          AND (
              CAST(:start_date AS DATE) IS NULL
              OR payment_date >= CAST(:start_date AS DATE)
          )
          AND (
              CAST(:end_date AS DATE) IS NULL
              OR payment_date < CAST(:end_date AS DATE) + INTERVAL '1 day'
          )

        UNION ALL

        SELECT
            DATE_TRUNC('month', refund_date)::DATE AS month,
            'customer_refunds' AS movement_type,
            amount_cents,
            'outflow' AS direction
        FROM sales_refunds
        WHERE dataset_version_id = :dataset_version_id
          AND status = 'successful'
          AND (
              CAST(:start_date AS DATE) IS NULL
              OR refund_date >= CAST(:start_date AS DATE)
          )
          AND (
              CAST(:end_date AS DATE) IS NULL
              OR refund_date < CAST(:end_date AS DATE) + INTERVAL '1 day'
          )

        UNION ALL

        SELECT
            DATE_TRUNC('month', payment_date)::DATE AS month,
            'expense_payments' AS movement_type,
            amount_cents,
            'outflow' AS direction
        FROM expense_payments
        WHERE dataset_version_id = :dataset_version_id
          AND status = 'successful'
          AND (
              CAST(:start_date AS DATE) IS NULL
              OR payment_date >= CAST(:start_date AS DATE)
          )
          AND (
              CAST(:end_date AS DATE) IS NULL
              OR payment_date < CAST(:end_date AS DATE) + INTERVAL '1 day'
          )

        UNION ALL

        SELECT
            DATE_TRUNC('month', payment_date)::DATE AS month,
            'supplier_payments' AS movement_type,
            amount_cents,
            'outflow' AS direction
        FROM supplier_payments
        WHERE dataset_version_id = :dataset_version_id
          AND status = 'successful'
          AND (
              CAST(:start_date AS DATE) IS NULL
              OR payment_date >= CAST(:start_date AS DATE)
          )
          AND (
              CAST(:end_date AS DATE) IS NULL
              OR payment_date < CAST(:end_date AS DATE) + INTERVAL '1 day'
          )
    """

    query = f"""
        SELECT
            month,
            movement_type,
            direction,
            SUM(amount_cents) AS amount_cents,
            COUNT(*) AS transaction_count
        FROM (
            {cash_movements_query}
        ) AS cash_movements
        GROUP BY month, movement_type, direction
        ORDER BY month, movement_type
    """

    rows = execute_query(query, parameters)

    movement_types = {
        "customer_collections": "inflow",
        "customer_refunds": "outflow",
        "expense_payments": "outflow",
        "supplier_payments": "outflow",
    }

    totals = {
        movement_type: {
            "amount_cents": 0,
            "transaction_count": 0,
        }
        for movement_type in movement_types
    }

    monthly_data: dict[str, dict[str, Any]] = {}

    for row in rows:
        movement_type = row["movement_type"]
        month = row["month"].isoformat()
        amount_cents = int(row["amount_cents"])
        transaction_count = int(row["transaction_count"])

        totals[movement_type]["amount_cents"] += amount_cents
        totals[movement_type]["transaction_count"] += transaction_count

        if month not in monthly_data:
            monthly_data[month] = {
                "month": month,
                "customer_collections_cents": 0,
                "customer_refunds_cents": 0,
                "expense_payments_cents": 0,
                "supplier_payments_cents": 0,
                "total_inflows_cents": 0,
                "total_outflows_cents": 0,
                "net_cash_movement_cents": 0,
            }

        monthly_data[month][f"{movement_type}_cents"] += amount_cents

        if row["direction"] == "inflow":
            monthly_data[month]["total_inflows_cents"] += amount_cents
        else:
            monthly_data[month]["total_outflows_cents"] += amount_cents

    total_inflows_cents = totals["customer_collections"]["amount_cents"]

    total_outflows_cents = sum(
        totals[movement_type]["amount_cents"]
        for movement_type in movement_types
        if movement_types[movement_type] == "outflow"
    )

    net_cash_movement_cents = (
        total_inflows_cents - total_outflows_cents
    )

    for month_data in monthly_data.values():
        month_data["net_cash_movement_cents"] = (
            month_data["total_inflows_cents"]
            - month_data["total_outflows_cents"]
        )

        for key, value in list(month_data.items()):
            if key.endswith("_cents"):
                month_data[key.removesuffix("_cents")] = round(
                    value / 100, 2
                )

    def format_movement(movement_type: str) -> dict[str, Any]:
        amount_cents = totals[movement_type]["amount_cents"]

        return {
            "amount_cents": amount_cents,
            "amount": round(amount_cents / 100, 2),
            "transaction_count": totals[movement_type]["transaction_count"],
        }

    return {
        "dataset_version_id": dataset_version_id,

        "period": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },

        "customer_collections": format_movement(
            "customer_collections"
        ),

        "customer_refunds": format_movement(
            "customer_refunds"
        ),

        "expense_payments": format_movement(
            "expense_payments"
        ),

        "supplier_payments": format_movement(
            "supplier_payments"
        ),

        "total_inflows_cents": total_inflows_cents,
        "total_inflows": round(total_inflows_cents / 100, 2),

        "total_outflows_cents": total_outflows_cents,
        "total_outflows": round(total_outflows_cents / 100, 2),

        "net_cash_movement_cents": net_cash_movement_cents,
        "net_cash_movement": round(
            net_cash_movement_cents / 100, 2
        ),

        "monthly_trend": list(monthly_data.values()),

        "cash_flow_coverage": {
            "included_sources": [
                "sales_payments",
                "sales_refunds",
                "expense_payments",
                "supplier_payments",
            ],
            "recognition_basis": "successful payment date",
            "excludes": [
                "pending, failed and reversed payments",
                "opening account balances",
                "transfers between financial accounts",
                "other cash movements not represented in these payment tables",
            ],
        },

        "currency": "USD",
    }
