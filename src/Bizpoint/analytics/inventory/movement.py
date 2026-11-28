from datetime import date
from typing import Any

from Bizpoint.analytics.common.query import execute_query


def get_inventory_movement_metrics(
    dataset_version_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """
    Analyse inventory movements by type and month.

    Positive quantities:
        purchase_receipt
        customer_return

    Negative quantities:
        sale

    Movement costs use recorded unit costs in integer cents.
    """

    if not dataset_version_id or not isinstance(dataset_version_id, str):
        raise ValueError("A valid dataset_version_id is required.")

    if start_date is not None and not isinstance(start_date, date):
        raise TypeError("start_date must be a datetime.date or None.")

    if end_date is not None and not isinstance(end_date, date):
        raise TypeError("end_date must be a datetime.date or None.")

    if start_date and end_date and start_date > end_date:
        raise ValueError("start_date cannot be later than end_date.")

    parameters = {
        "dataset_version_id": dataset_version_id,
        "start_date": start_date,
        "end_date": end_date,
    }

    summary_query = """
        SELECT
            movement_type,
            COUNT(*) AS movement_count,
            SUM(ABS(quantity::BIGINT)) AS units_moved,
            SUM(
                ABS(quantity::BIGINT) * unit_cost_cents
            ) AS movement_cost_cents,
            MIN(movement_date) AS first_movement_date,
            MAX(movement_date) AS last_movement_date
        FROM inventory_movements
        WHERE dataset_version_id = :dataset_version_id
          AND (
              CAST(:start_date AS DATE) IS NULL
              OR movement_date >= CAST(:start_date AS DATE)
          )
          AND (
              CAST(:end_date AS DATE) IS NULL
              OR movement_date < CAST(:end_date AS DATE)
                 + INTERVAL '1 day'
          )
        GROUP BY movement_type
        ORDER BY movement_type
    """

    monthly_query = """
        SELECT
            DATE_TRUNC('month', movement_date)::DATE AS month,
            movement_type,
            COUNT(*) AS movement_count,
            SUM(ABS(quantity::BIGINT)) AS units_moved,
            SUM(
                ABS(quantity::BIGINT) * unit_cost_cents
            ) AS movement_cost_cents
        FROM inventory_movements
        WHERE dataset_version_id = :dataset_version_id
          AND (
              CAST(:start_date AS DATE) IS NULL
              OR movement_date >= CAST(:start_date AS DATE)
          )
          AND (
              CAST(:end_date AS DATE) IS NULL
              OR movement_date < CAST(:end_date AS DATE)
                 + INTERVAL '1 day'
          )
        GROUP BY
            DATE_TRUNC('month', movement_date)::DATE,
            movement_type
        ORDER BY month, movement_type
    """

    movement_rows = execute_query(summary_query, parameters)
    monthly_rows = execute_query(monthly_query, parameters)

    movement_types = {
        "purchase_receipt": {
            "movement_count": 0,
            "units_moved": 0,
            "movement_cost_cents": 0,
        },
        "sale": {
            "movement_count": 0,
            "units_moved": 0,
            "movement_cost_cents": 0,
        },
        "customer_return": {
            "movement_count": 0,
            "units_moved": 0,
            "movement_cost_cents": 0,
        },
    }

    for row in movement_rows:
        movement_type = row["movement_type"]

        if movement_type not in movement_types:
            raise ValueError(
                f"Unexpected inventory movement type: {movement_type}"
            )

        movement_types[movement_type] = {
            "movement_count": int(row["movement_count"] or 0),
            "units_moved": int(row["units_moved"] or 0),
            "movement_cost_cents": int(
                row["movement_cost_cents"] or 0
            ),
            "first_movement_date": (
                row["first_movement_date"].isoformat()
                if row["first_movement_date"]
                else None
            ),
            "last_movement_date": (
                row["last_movement_date"].isoformat()
                if row["last_movement_date"]
                else None
            ),
        }

    receipts = movement_types["purchase_receipt"]
    sales = movement_types["sale"]
    returns = movement_types["customer_return"]

    total_movements = sum(
        item["movement_count"] for item in movement_types.values()
    )

    total_receipt_units = receipts["units_moved"]
    total_sale_units = sales["units_moved"]
    total_return_units = returns["units_moved"]

    net_stock_movement = (
        total_receipt_units
        + total_return_units
        - total_sale_units
    )

    receipt_cost = receipts["movement_cost_cents"]
    sale_cost = sales["movement_cost_cents"]
    return_cost = returns["movement_cost_cents"]

    net_inventory_cost_movement = (
        receipt_cost + return_cost - sale_cost
    )

    monthly_trend = []

    for row in monthly_rows:
        movement_cost_cents = int(
            row["movement_cost_cents"] or 0
        )

        monthly_trend.append({
            "month": row["month"].isoformat(),
            "movement_type": row["movement_type"],
            "movement_count": int(row["movement_count"]),
            "units_moved": int(row["units_moved"] or 0),
            "movement_cost_cents": movement_cost_cents,
            "movement_cost_dollars": round(
                movement_cost_cents / 100, 2
            ),
        })

    monthly_movement_count = sum(
        item["movement_count"] for item in monthly_trend
    )

    monthly_movement_cost = sum(
        item["movement_cost_cents"] for item in monthly_trend
    )

    reconciliation = {
        "movement_counts_match_monthly_trend": (
            total_movements == monthly_movement_count
        ),
        "movement_cost_matches_monthly_trend": (
            sum(
                item["movement_cost_cents"]
                for item in movement_types.values()
            ) == monthly_movement_cost
        ),
        "net_stock_movement_reconciles": (
            net_stock_movement
            == total_receipt_units
            + total_return_units
            - total_sale_units
        ),
        "net_inventory_cost_movement_reconciles": (
            net_inventory_cost_movement
            == receipt_cost + return_cost - sale_cost
        ),
    }

    reconciliation["all_checks_passed"] = all(
        reconciliation.values()
    )

    return {
        "metadata": {
            "dataset_version_id": dataset_version_id,
            "start_date": (
                start_date.isoformat() if start_date else None
            ),
            "end_date": (
                end_date.isoformat() if end_date else None
            ),
            "currency": "USD",
        },
        "summary": {
            "total_movements": total_movements,
            "total_receipt_units": total_receipt_units,
            "total_sale_units": total_sale_units,
            "total_return_units": total_return_units,
            "net_stock_movement": net_stock_movement,
            "receipt_cost_cents": receipt_cost,
            "receipt_cost_dollars": round(receipt_cost / 100, 2),
            "sale_cost_cents": sale_cost,
            "sale_cost_dollars": round(sale_cost / 100, 2),
            "return_cost_cents": return_cost,
            "return_cost_dollars": round(return_cost / 100, 2),
            "net_inventory_cost_movement_cents": (
                net_inventory_cost_movement
            ),
            "net_inventory_cost_movement_dollars": round(
                net_inventory_cost_movement / 100, 2
            ),
        },
        "by_movement_type": movement_types,
        "monthly_trend": monthly_trend,
        "reconciliation": reconciliation,
    }
