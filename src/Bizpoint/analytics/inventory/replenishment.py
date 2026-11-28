from datetime import date
from math import ceil
from typing import Any

from Bizpoint.analytics.common.query import execute_query


def get_inventory_replenishment(
    dataset_version_id: str,
    as_of_date: date | None = None,
    demand_window_days: int = 90,
    lead_time_days: int = 11,
    safety_stock_days: int = 7,
    review_period_days: int = 30,
) -> dict[str, Any]:
    """
    Calculate product/store replenishment recommendations.

    Demand is estimated from historical sale inventory movements.
    Current stock is reconstructed from inventory movements.
    Incoming supply includes outstanding submitted and partially
    received purchase-order quantities.

    This function is read-only. It does not create purchase orders.
    """

    if not dataset_version_id or not isinstance(dataset_version_id, str):
        raise ValueError("A valid dataset_version_id is required.")

    if as_of_date is not None and not isinstance(as_of_date, date):
        raise TypeError("as_of_date must be a datetime.date or None.")

    parameters_to_validate = {
        "demand_window_days": demand_window_days,
        "lead_time_days": lead_time_days,
        "safety_stock_days": safety_stock_days,
        "review_period_days": review_period_days,
    }

    for name, value in parameters_to_validate.items():
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"{name} must be a positive integer.")

    query = """
        WITH date_parameters AS (
            SELECT
                COALESCE(
                    CAST(:as_of_date AS DATE),
                    (
                        SELECT MAX(movement_date)::DATE
                        FROM inventory_movements
                        WHERE dataset_version_id = :dataset_version_id
                    )
                ) AS effective_date
        ),

        stock_positions AS (
            SELECT
                im.product_id,
                im.store_id,

                SUM(
                    CASE
                        WHEN im.movement_type IN (
                            'purchase_receipt',
                            'customer_return'
                        )
                        THEN im.quantity
                        WHEN im.movement_type = 'sale'
                        THEN im.quantity
                        ELSE 0
                    END
                ) AS on_hand_quantity

            FROM inventory_movements im
            CROSS JOIN date_parameters dp

            WHERE im.dataset_version_id = :dataset_version_id
              AND im.movement_date < dp.effective_date + INTERVAL '1 day'

            GROUP BY
                im.product_id,
                im.store_id
        ),

        sales_demand AS (
            SELECT
                im.product_id,
                im.store_id,
                SUM(ABS(im.quantity::BIGINT)) AS units_sold

            FROM inventory_movements im
            CROSS JOIN date_parameters dp

            WHERE im.dataset_version_id = :dataset_version_id
              AND im.movement_type = 'sale'
              AND im.movement_date >= (
                  dp.effective_date
                  - (:demand_window_days - 1) * INTERVAL '1 day'
              )
              AND im.movement_date < (
                  dp.effective_date + INTERVAL '1 day'
              )

            GROUP BY
                im.product_id,
                im.store_id
        ),

        received_by_order_item AS (
            SELECT
                gri.purchase_order_item_id,
                SUM(gri.quantity_received) AS quantity_received

            FROM goods_receipt_items gri

            JOIN goods_receipts gr
                ON gr.id = gri.goods_receipt_id
                AND gr.dataset_version_id = gri.dataset_version_id

            WHERE gri.dataset_version_id = :dataset_version_id
              AND gr.status = 'accepted'

            GROUP BY gri.purchase_order_item_id
        ),

        outstanding_supply AS (
            SELECT
                poi.product_id,
                po.store_id,

                SUM(
                    GREATEST(
                        poi.quantity - COALESCE(
                            r.quantity_received, 0
                        ),
                        0
                    )
                ) AS outstanding_quantity

            FROM purchase_orders po

            JOIN purchase_order_items poi
                ON poi.purchase_order_id = po.id
                AND poi.dataset_version_id = po.dataset_version_id

            LEFT JOIN received_by_order_item r
                ON r.purchase_order_item_id = poi.id

            WHERE po.dataset_version_id = :dataset_version_id
              AND po.status IN ('submitted', 'partially_received')

            GROUP BY
                poi.product_id,
                po.store_id
        ),

        product_store_universe AS (
            SELECT product_id, store_id FROM stock_positions

            UNION

            SELECT product_id, store_id FROM sales_demand

            UNION

            SELECT product_id, store_id FROM outstanding_supply
        )

        SELECT
            dp.effective_date AS as_of_date,

            p.id AS product_id,
            p.sku,
            p.product_name,
            p.product_status,
            p.is_active,

            s.id AS store_id,
            s.store_name,
            s.store_code,

            COALESCE(sp.on_hand_quantity, 0) AS on_hand_quantity,

            COALESCE(sd.units_sold, 0) AS units_sold_in_window,

            COALESCE(os.outstanding_quantity, 0)
                AS outstanding_quantity

        FROM product_store_universe u

        CROSS JOIN date_parameters dp

        JOIN products p
            ON p.id = u.product_id
            AND p.dataset_version_id = :dataset_version_id

        JOIN stores s
            ON s.id = u.store_id
            AND s.dataset_version_id = :dataset_version_id

        LEFT JOIN stock_positions sp
            ON sp.product_id = u.product_id
            AND sp.store_id = u.store_id

        LEFT JOIN sales_demand sd
            ON sd.product_id = u.product_id
            AND sd.store_id = u.store_id

        LEFT JOIN outstanding_supply os
            ON os.product_id = u.product_id
            AND os.store_id = u.store_id

        ORDER BY
            s.store_name,
            p.product_name
    """

    rows = execute_query(
        query,
        {
            "dataset_version_id": dataset_version_id,
            "as_of_date": as_of_date,
            "demand_window_days": demand_window_days,
        },
    )

    if not rows:
        raise ValueError(
            "No inventory, sales or outstanding procurement records "
            "were found for this dataset."
        )

    positions = []

    for row in rows:
        item = dict(row)

        on_hand = int(item["on_hand_quantity"] or 0)
        units_sold = int(item["units_sold_in_window"] or 0)
        outstanding = int(item["outstanding_quantity"] or 0)

        daily_demand = units_sold / demand_window_days

        inventory_position = on_hand + outstanding

        reorder_point = ceil(
            daily_demand * (lead_time_days + safety_stock_days)
        )

        target_stock = ceil(
            daily_demand * (
                lead_time_days
                + safety_stock_days
                + review_period_days
            )
        )

        if daily_demand > 0:
            days_of_stock = round(on_hand / daily_demand, 2)
            days_of_inventory_position = round(
                inventory_position / daily_demand, 2
            )
        else:
            days_of_stock = None
            days_of_inventory_position = None

        if daily_demand == 0:
            status = "no_recent_demand"
        elif on_hand <= 0 or days_of_stock <= lead_time_days:
            status = "stockout_risk"
        elif inventory_position <= reorder_point:
            status = "reorder_required"
        else:
            status = "adequate_stock"

        suggested_quantity = 0

        if (
            daily_demand > 0
            and inventory_position <= reorder_point
        ):
            suggested_quantity = max(
                target_stock - inventory_position,
                0,
            )

        item.update({
            "on_hand_quantity": on_hand,
            "units_sold_in_window": units_sold,
            "outstanding_quantity": outstanding,
            "average_daily_demand": round(daily_demand, 4),
            "inventory_position": inventory_position,
            "reorder_point": reorder_point,
            "target_stock": target_stock,
            "days_of_stock": days_of_stock,
            "days_of_inventory_position": days_of_inventory_position,
            "stockout_risk": status == "stockout_risk",
            "reorder_required": suggested_quantity > 0,
            "suggested_reorder_quantity": suggested_quantity,
            "status": status,
        })

        positions.append(item)

    total_on_hand = sum(
        item["on_hand_quantity"] for item in positions
    )

    total_outstanding = sum(
        item["outstanding_quantity"] for item in positions
    )

    total_demand = sum(
        item["units_sold_in_window"] for item in positions
    )

    total_suggested = sum(
        item["suggested_reorder_quantity"] for item in positions
    )

    status_counts = {
        status: sum(
            item["status"] == status for item in positions
        )
        for status in (
            "stockout_risk",
            "reorder_required",
            "adequate_stock",
            "no_recent_demand",
        )
    }

    summary = {
        "product_store_positions": len(positions),
        "products_with_recent_demand": sum(
            item["units_sold_in_window"] > 0
            for item in positions
        ),
        "total_units_on_hand": total_on_hand,
        "total_units_sold_in_demand_window": total_demand,
        "average_daily_demand": round(
            total_demand / demand_window_days, 2
        ),
        "outstanding_purchase_order_units": total_outstanding,
        "total_inventory_position": total_on_hand + total_outstanding,
        "stockout_risk_positions": status_counts["stockout_risk"],
        "reorder_required_positions": status_counts["reorder_required"],
        "adequate_stock_positions": status_counts["adequate_stock"],
        "no_recent_demand_positions": status_counts["no_recent_demand"],
        "total_suggested_reorder_units": total_suggested,
    }

    reconciliation = {
        "inventory_position_reconciles": (
            summary["total_inventory_position"]
            == total_on_hand + total_outstanding
        ),
        "suggested_quantity_is_non_negative": all(
            item["suggested_reorder_quantity"] >= 0
            for item in positions
        ),
        "demand_is_non_negative": all(
            item["units_sold_in_window"] >= 0
            for item in positions
        ),
        "status_counts_reconcile": (
            sum(status_counts.values()) == len(positions)
        ),
    }

    reconciliation["all_checks_passed"] = all(
        reconciliation.values()
    )

    recommendations = [
        item for item in positions
        if item["suggested_reorder_quantity"] > 0
    ]

    recommendations.sort(
        key=lambda item: (
            item["status"] != "stockout_risk",
            -item["suggested_reorder_quantity"],
        )
    )

    stockout_risk_positions = [
        item for item in positions
        if item["stockout_risk"]
    ]

    stockout_risk_positions.sort(
        key=lambda item: (
            item["days_of_stock"]
            if item["days_of_stock"] is not None
            else float("inf")
        )
    )

    effective_date = rows[0]["as_of_date"]

    return {
        "metadata": {
            "dataset_version_id": dataset_version_id,
            "as_of_date": (
                effective_date.isoformat()
                if effective_date is not None
                else None
            ),
            "currency": "USD",
            "demand_window_days": demand_window_days,
            "lead_time_days": lead_time_days,
            "safety_stock_days": safety_stock_days,
            "review_period_days": review_period_days,
            "replenishment_policy": (
                "Demand-based reorder point with safety stock "
                "and outstanding purchase-order coverage"
            ),
        },
        "summary": summary,
        "status_counts": status_counts,
        "positions": positions,
        "reorder_recommendations": recommendations,
        "stockout_risk_positions": stockout_risk_positions,
        "reconciliation": reconciliation,
    }
