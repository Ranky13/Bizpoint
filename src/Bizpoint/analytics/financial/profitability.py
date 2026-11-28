from datetime import date
from typing import Any

from Bizpoint.analytics.common.query import execute_query
from Bizpoint.analytics.financial.revenue import get_revenue_metrics
from Bizpoint.analytics.financial.expenses import get_expense_metrics


def get_profitability_metrics(
    dataset_version_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """
    Calculate business profitability.

    Revenue:
        Completed sales less completed returns.

    COGS:
        Sale inventory costs less returned inventory costs.

    Operating result:
        Gross profit less approved operating expenses.

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

    revenue = get_revenue_metrics(
        dataset_version_id,
        start_date,
        end_date,
    )

    expenses = get_expense_metrics(
        dataset_version_id,
        start_date,
        end_date,
    )

    cogs_query = """
        SELECT
            COALESCE(
                SUM(ABS(quantity::BIGINT) * unit_cost_cents)
                    FILTER (WHERE movement_type = 'sale'),
                0
            ) AS sale_cogs_cents,

            COALESCE(
                SUM(ABS(quantity::BIGINT) * unit_cost_cents)
                    FILTER (WHERE movement_type = 'customer_return'),
                0
            ) AS returned_inventory_cost_cents

        FROM inventory_movements

        WHERE dataset_version_id = :dataset_version_id
          AND movement_type IN ('sale', 'customer_return')
          AND (
              CAST(:start_date AS DATE) IS NULL
              OR movement_date >= CAST(:start_date AS DATE)
          )
          AND (
              CAST(:end_date AS DATE) IS NULL
              OR movement_date < CAST(:end_date AS DATE) + INTERVAL '1 day'
          )
    """

    cogs_rows = execute_query(cogs_query, parameters)
    cogs = cogs_rows[0]

    gross_revenue_cents = revenue["gross_revenue_cents"]
    sales_returns_cents = revenue["sales_returns_cents"]
    net_revenue_cents = revenue["net_revenue_cents"]

    sale_cogs_cents = int(cogs["sale_cogs_cents"])
    returned_inventory_cost_cents = int(
        cogs["returned_inventory_cost_cents"]
    )

    net_cogs_cents = (
        sale_cogs_cents - returned_inventory_cost_cents
    )

    gross_profit_cents = net_revenue_cents - net_cogs_cents

    operating_expenses_cents = expenses["total_expenses_cents"]

    operating_result_cents = (
        gross_profit_cents - operating_expenses_cents
    )

    def to_dollars(amount_cents: int) -> float:
        return round(amount_cents / 100, 2)

    def calculate_margin(
        profit_cents: int,
        revenue_cents: int,
    ) -> float | None:
        if revenue_cents == 0:
            return None

        return round(profit_cents / revenue_cents * 100, 2)

    return {
        "dataset_version_id": dataset_version_id,

        "period": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },

        "revenue": {
            "gross_revenue_cents": gross_revenue_cents,
            "sales_returns_cents": sales_returns_cents,
            "net_revenue_cents": net_revenue_cents,
            "gross_revenue": to_dollars(gross_revenue_cents),
            "sales_returns": to_dollars(sales_returns_cents),
            "net_revenue": to_dollars(net_revenue_cents),
        },

        "cost_of_goods_sold": {
            "sale_cogs_cents": sale_cogs_cents,
            "returned_inventory_cost_cents": returned_inventory_cost_cents,
            "net_cogs_cents": net_cogs_cents,
            "sale_cogs": to_dollars(sale_cogs_cents),
            "returned_inventory_cost": to_dollars(
                returned_inventory_cost_cents
            ),
            "net_cogs": to_dollars(net_cogs_cents),
        },

        "gross_profit": {
            "amount_cents": gross_profit_cents,
            "amount": to_dollars(gross_profit_cents),
            "margin_percentage": calculate_margin(
                gross_profit_cents,
                net_revenue_cents,
            ),
        },

        "operating_expenses": {
            "amount_cents": operating_expenses_cents,
            "amount": to_dollars(operating_expenses_cents),
            "expense_count": expenses["expense_count"],
        },

        "operating_result": {
            "amount_cents": operating_result_cents,
            "amount": to_dollars(operating_result_cents),
            "margin_percentage": calculate_margin(
                operating_result_cents,
                net_revenue_cents,
            ),
            "status": (
                "profit" if operating_result_cents > 0
                else "loss" if operating_result_cents < 0
                else "break_even"
            ),
        },

        "currency": "USD",
    }
