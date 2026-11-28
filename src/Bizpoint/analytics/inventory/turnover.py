from datetime import date
from typing import Any

from Bizpoint.analytics.common.query import execute_query


def get_inventory_turnover(
    dataset_version_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """
    Calculate inventory turnover and days inventory outstanding.

    Average inventory is calculated from daily closing inventory
    valuations, including the opening balance before the period.

    Inventory turnover = Net COGS / Average inventory value.
    DIO = Period days / Inventory turnover.

    This function is read-only.
    """

    if not dataset_version_id or not isinstance(dataset_version_id, str):
        raise ValueError("A valid dataset_version_id is required.")

    for name, value in (
        ("start_date", start_date),
        ("end_date", end_date),
    ):
        if value is not None and not isinstance(value, date):
            raise TypeError(f"{name} must be a datetime.date or None.")

    if start_date is not None and end_date is not None:
        if start_date > end_date:
            raise ValueError("start_date cannot be later than end_date.")

    query = """
        WITH latest_date AS (
            SELECT MAX(movement_date)::DATE AS latest_date
            FROM inventory_movements
            WHERE dataset_version_id = :dataset_version_id
        ),

        date_parameters AS (
            SELECT
                COALESCE(
                    CAST(:start_date AS DATE),
                    (latest_date - INTERVAL '364 days')::DATE
                ) AS period_start,

                COALESCE(
                    CAST(:end_date AS DATE),
                    latest_date
                ) AS period_end

            FROM latest_date
        ),

        movement_values AS (
            SELECT
                im.product_id,
                im.store_id,
                im.movement_date::DATE AS movement_day,
                im.movement_type,

                CASE
                    WHEN im.movement_type IN (
                        'purchase_receipt',
                        'customer_return'
                    )
                    THEN ABS(im.quantity::BIGINT) * im.unit_cost_cents

                    WHEN im.movement_type = 'sale'
                    THEN -(
                        ABS(im.quantity::BIGINT) * im.unit_cost_cents
                    )

                    ELSE 0
                END AS inventory_value_delta_cents,

                CASE
                    WHEN im.movement_type = 'sale'
                    THEN ABS(im.quantity::BIGINT) * im.unit_cost_cents
                    ELSE 0
                END AS sale_cogs_cents,

                CASE
                    WHEN im.movement_type = 'customer_return'
                    THEN ABS(im.quantity::BIGINT) * im.unit_cost_cents
                    ELSE 0
                END AS returned_inventory_cost_cents

            FROM inventory_movements im

            WHERE im.dataset_version_id = :dataset_version_id
        ),

        product_store_universe AS (
            SELECT DISTINCT
                product_id,
                store_id
            FROM movement_values
        ),

        opening_balances AS (
            SELECT
                mv.product_id,
                mv.store_id,
                SUM(mv.inventory_value_delta_cents)
                    AS opening_inventory_value_cents

            FROM movement_values mv
            CROSS JOIN date_parameters dp

            WHERE mv.movement_day < dp.period_start

            GROUP BY
                mv.product_id,
                mv.store_id
        ),

        daily_movements AS (
            SELECT
                mv.product_id,
                mv.store_id,
                mv.movement_day,

                SUM(mv.inventory_value_delta_cents)
                    AS inventory_value_delta_cents

            FROM movement_values mv
            CROSS JOIN date_parameters dp

            WHERE mv.movement_day BETWEEN
                dp.period_start AND dp.period_end

            GROUP BY
                mv.product_id,
                mv.store_id,
                mv.movement_day
        ),

        calendar AS (
            SELECT
                generate_series(
                    dp.period_start,
                    dp.period_end,
                    INTERVAL '1 day'
                )::DATE AS snapshot_date

            FROM date_parameters dp
        ),

        daily_inventory_balances AS (
            SELECT
                u.product_id,
                u.store_id,
                c.snapshot_date,

                COALESCE(
                    ob.opening_inventory_value_cents,
                    0
                )
                +
                SUM(
                    COALESCE(
                        dm.inventory_value_delta_cents,
                        0
                    )
                ) OVER (
                    PARTITION BY u.product_id, u.store_id
                    ORDER BY c.snapshot_date
                    ROWS BETWEEN UNBOUNDED PRECEDING
                    AND CURRENT ROW
                ) AS inventory_value_cents

            FROM product_store_universe u

            CROSS JOIN calendar c

            LEFT JOIN opening_balances ob
                ON ob.product_id = u.product_id
                AND ob.store_id = u.store_id

            LEFT JOIN daily_movements dm
                ON dm.product_id = u.product_id
                AND dm.store_id = u.store_id
                AND dm.movement_day = c.snapshot_date
        ),

        average_inventory AS (
            SELECT
                product_id,
                store_id,

                AVG(inventory_value_cents)
                    AS average_inventory_value_cents,

                MAX(inventory_value_cents)
                    FILTER (
                        WHERE snapshot_date = (
                            SELECT period_end FROM date_parameters
                        )
                    ) AS ending_inventory_value_cents

            FROM daily_inventory_balances

            GROUP BY
                product_id,
                store_id
        ),

        period_costs AS (
            SELECT
                mv.product_id,
                mv.store_id,

                SUM(mv.sale_cogs_cents) AS sale_cogs_cents,

                SUM(mv.returned_inventory_cost_cents)
                    AS returned_inventory_cost_cents

            FROM movement_values mv
            CROSS JOIN date_parameters dp

            WHERE mv.movement_day BETWEEN
                dp.period_start AND dp.period_end

            GROUP BY
                mv.product_id,
                mv.store_id
        )

        SELECT
            p.id AS product_id,
            p.sku,
            p.product_name,

            pc.category_name,

            s.id AS store_id,
            s.store_name,
            s.store_code,

            COALESCE(
                ai.average_inventory_value_cents, 0
            ) AS average_inventory_value_cents,

            COALESCE(
                ai.ending_inventory_value_cents, 0
            ) AS ending_inventory_value_cents,

            COALESCE(
                costs.sale_cogs_cents, 0
            ) AS sale_cogs_cents,

            COALESCE(
                costs.returned_inventory_cost_cents, 0
            ) AS returned_inventory_cost_cents,

            COALESCE(costs.sale_cogs_cents, 0)
            - COALESCE(
                costs.returned_inventory_cost_cents, 0
            ) AS net_cogs_cents,

            dp.period_start,
            dp.period_end,

            (
                dp.period_end - dp.period_start + 1
            ) AS period_days

        FROM product_store_universe u

        JOIN products p
            ON p.id = u.product_id
            AND p.dataset_version_id = :dataset_version_id

        JOIN stores s
            ON s.id = u.store_id
            AND s.dataset_version_id = :dataset_version_id

        LEFT JOIN product_categories pc
            ON pc.id = p.category_id
            AND pc.dataset_version_id = p.dataset_version_id

        LEFT JOIN average_inventory ai
            ON ai.product_id = u.product_id
            AND ai.store_id = u.store_id

        LEFT JOIN period_costs costs
            ON costs.product_id = u.product_id
            AND costs.store_id = u.store_id

        CROSS JOIN date_parameters dp

        ORDER BY
            p.product_name,
            s.store_name
    """

    rows = execute_query(
        query,
        {
            "dataset_version_id": dataset_version_id,
            "start_date": start_date,
            "end_date": end_date,
        },
    )

    if not rows:
        raise ValueError(
            "No inventory movement records were found for this dataset."
        )

    def calculate_metrics(
        average_inventory_cents: int,
        sale_cogs_cents: int,
        returned_cost_cents: int,
        period_days: int,
    ) -> dict[str, Any]:

        net_cogs_cents = sale_cogs_cents - returned_cost_cents

        average_inventory_cents = round(average_inventory_cents)

        if average_inventory_cents > 0:
            turnover_ratio = (
                net_cogs_cents / average_inventory_cents
            )
        else:
            turnover_ratio = None

        if turnover_ratio is not None and turnover_ratio > 0:
            dio = period_days / turnover_ratio
        else:
            dio = None

        return {
            "average_inventory_value_cents": average_inventory_cents,
            "average_inventory_value_dollars": round(
                average_inventory_cents / 100, 2
            ),
            "ending_inventory_value_cents": None,
            "sale_cogs_cents": sale_cogs_cents,
            "sale_cogs_dollars": round(sale_cogs_cents / 100, 2),
            "returned_inventory_cost_cents": returned_cost_cents,
            "returned_inventory_cost_dollars": round(
                returned_cost_cents / 100, 2
            ),
            "net_cogs_cents": net_cogs_cents,
            "net_cogs_dollars": round(net_cogs_cents / 100, 2),
            "inventory_turnover_ratio": (
                round(turnover_ratio, 4)
                if turnover_ratio is not None
                else None
            ),
            "days_inventory_outstanding": (
                round(dio, 2) if dio is not None else None
            ),
        }

    def aggregate_records(
        records: list[dict[str, Any]],
        keys: tuple[str, ...],
    ) -> list[dict[str, Any]]:

        groups: dict[tuple, list[dict[str, Any]]] = {}

        for record in records:
            group_key = tuple(record[key] for key in keys)
            groups.setdefault(group_key, []).append(record)

        results = []

        for group_key, group_records in groups.items():
            result = {
                key: value
                for key, value in zip(keys, group_key)
            }

            average_inventory = sum(
                item["average_inventory_value_cents"]
                for item in group_records
            )

            ending_inventory = sum(
                item["ending_inventory_value_cents"]
                for item in group_records
            )

            sale_cogs = sum(
                item["sale_cogs_cents"]
                for item in group_records
            )

            returned_cost = sum(
                item["returned_inventory_cost_cents"]
                for item in group_records
            )

            metrics = calculate_metrics(
                average_inventory,
                sale_cogs,
                returned_cost,
                period_days,
            )

            metrics["ending_inventory_value_cents"] = ending_inventory
            metrics["ending_inventory_value_dollars"] = round(
                ending_inventory / 100, 2
            )

            result.update(metrics)
            result["product_store_count"] = len(group_records)

            results.append(result)

        return results

    first_row = rows[0]

    period_days = int(first_row["period_days"])

    positions = []

    for row in rows:
        item = dict(row)

        item["average_inventory_value_cents"] = round(
            float(item["average_inventory_value_cents"] or 0)
        )

        item["ending_inventory_value_cents"] = int(
            item["ending_inventory_value_cents"] or 0
        )

        for field in (
            "sale_cogs_cents",
            "returned_inventory_cost_cents",
            "net_cogs_cents",
        ):
            item[field] = int(item[field] or 0)

        metrics = calculate_metrics(
            item["average_inventory_value_cents"],
            item["sale_cogs_cents"],
            item["returned_inventory_cost_cents"],
            period_days,
        )

        metrics["ending_inventory_value_cents"] = (
            item["ending_inventory_value_cents"]
        )

        metrics["ending_inventory_value_dollars"] = round(
            item["ending_inventory_value_cents"] / 100, 2
        )

        item.update(metrics)

        item["inventory_turnover_status"] = (
            "not_calculable"
            if item["inventory_turnover_ratio"] is None
            else "no_turnover"
            if item["inventory_turnover_ratio"] <= 0
            else "slow_turnover"
            if item["days_inventory_outstanding"] > period_days
            else "turning_over"
        )

        positions.append(item)

    by_product = aggregate_records(
        positions,
        ("product_id", "sku", "product_name", "category_name"),
    )

    by_category = aggregate_records(
        positions,
        ("category_name",),
    )

    by_store = aggregate_records(
        positions,
        ("store_id", "store_name", "store_code"),
    )

    by_product_store = aggregate_records(
        positions,
        ("product_id", "sku", "product_name",
         "store_id", "store_name", "store_code"),
    )

    total_average_inventory = sum(
        item["average_inventory_value_cents"]
        for item in positions
    )

    total_ending_inventory = sum(
        item["ending_inventory_value_cents"]
        for item in positions
    )

    total_sale_cogs = sum(
        item["sale_cogs_cents"] for item in positions
    )

    total_returned_cost = sum(
        item["returned_inventory_cost_cents"]
        for item in positions
    )

    summary = calculate_metrics(
        total_average_inventory,
        total_sale_cogs,
        total_returned_cost,
        period_days,
    )

    summary["ending_inventory_value_cents"] = total_ending_inventory
    summary["ending_inventory_value_dollars"] = round(
        total_ending_inventory / 100, 2
    )

    summary["product_count"] = len(by_product)
    summary["store_count"] = len(by_store)
    summary["product_store_count"] = len(positions)
    summary["period_days"] = period_days

    reconciliation = {
        "net_cogs_reconciles": (
            summary["net_cogs_cents"]
            == summary["sale_cogs_cents"]
            - summary["returned_inventory_cost_cents"]
        ),
        "product_average_inventory_reconciles": (
            sum(
                item["average_inventory_value_cents"]
                for item in by_product
            )
            == total_average_inventory
        ),
        "store_average_inventory_reconciles": (
            sum(
                item["average_inventory_value_cents"]
                for item in by_store
            )
            == total_average_inventory
        ),
        "ending_inventory_reconciles": (
            total_ending_inventory
            == sum(
                item["ending_inventory_value_cents"]
                for item in positions
            )
        ),
        "product_cogs_reconciles": (
            sum(item["net_cogs_cents"] for item in by_product)
            == summary["net_cogs_cents"]
        ),
    }

    reconciliation["all_checks_passed"] = all(
        reconciliation.values()
    )

    return {
        "metadata": {
            "dataset_version_id": dataset_version_id,
            "start_date": first_row["period_start"].isoformat(),
            "end_date": first_row["period_end"].isoformat(),
            "period_days": period_days,
            "currency": "USD",
            "valuation_method": "Recorded inventory movement costs",
            "average_inventory_method": "Daily closing inventory valuation",
            "turnover_formula": "Net COGS / Average inventory value",
            "dio_formula": "Period days / Inventory turnover",
        },
        "summary": summary,
        "by_category": by_category,
        "by_store": by_store,
        "by_product": by_product,
        "by_product_store": by_product_store,
        "top_products_by_inventory_value": sorted(
            by_product,
            key=lambda item: item["ending_inventory_value_cents"],
            reverse=True,
        )[:10],
        "slowest_turning_products": sorted(
            [
                item for item in by_product
                if item["days_inventory_outstanding"] is not None
            ],
            key=lambda item: item["days_inventory_outstanding"],
            reverse=True,
        )[:10],
        "reconciliation": reconciliation,
    }
