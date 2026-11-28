from datetime import date
from typing import Any

from Bizpoint.analytics.financial.revenue import get_revenue_metrics
from Bizpoint.analytics.financial.expenses import get_expense_metrics
from Bizpoint.analytics.financial.profitability import get_profitability_metrics
from Bizpoint.analytics.financial.cash_flow import get_cash_flow_metrics
from Bizpoint.analytics.financial.budgets import get_budget_metrics


def _percentage(numerator: int, denominator: int) -> float | None:
    """Calculate a percentage safely using integer monetary values."""
    if denominator == 0:
        return None

    return round((numerator / denominator) * 100, 2)


def _money(amount_cents: int) -> dict[str, int | float]:
    """Return a monetary value in cents and display currency units."""
    return {
        "amount_cents": amount_cents,
        "amount": round(amount_cents / 100, 2),
    }


def get_financial_kpis(
    dataset_version_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """
    Consolidate financial analytics into one financial KPI report.

    This service reuses the existing financial analytics modules.
    It does not execute independent financial calculations from raw tables.

    Monetary values are stored and calculated in integer cents.
    Display values are returned in the dataset reporting currency.
    """

    if not dataset_version_id:
        raise ValueError("dataset_version_id is required.")

    if start_date and end_date and start_date > end_date:
        raise ValueError("start_date cannot be later than end_date.")

    # Reuse the existing financial analytics services.
    revenue = get_revenue_metrics(
        dataset_version_id,
        start_date=start_date,
        end_date=end_date,
    )

    expenses = get_expense_metrics(
        dataset_version_id,
        start_date=start_date,
        end_date=end_date,
    )

    profitability = get_profitability_metrics(
        dataset_version_id,
        start_date=start_date,
        end_date=end_date,
    )

    cash_flow = get_cash_flow_metrics(
        dataset_version_id,
        start_date=start_date,
        end_date=end_date,
    )

    budgets = get_budget_metrics(
        dataset_version_id,
        start_date=start_date,
        end_date=end_date,
    )

    # Validate that all services returned the requested dataset.
    services = {
        "revenue": revenue,
        "expenses": expenses,
        "profitability": profitability,
        "cash_flow": cash_flow,
        "budgets": budgets,
    }

    for service_name, result in services.items():
        if result["dataset_version_id"] != dataset_version_id:
            raise ValueError(
                f"{service_name} returned an unexpected dataset version."
            )

    # Extract financial amounts in integer cents.
    gross_revenue_cents = revenue["gross_revenue_cents"]
    sales_returns_cents = revenue["sales_returns_cents"]
    net_revenue_cents = revenue["net_revenue_cents"]

    sale_cogs_cents = (
        profitability["cost_of_goods_sold"]["sale_cogs_cents"]
    )

    returned_inventory_cost_cents = (
        profitability["cost_of_goods_sold"][
            "returned_inventory_cost_cents"
        ]
    )

    net_cogs_cents = (
        profitability["cost_of_goods_sold"]["net_cogs_cents"]
    )

    gross_profit_cents = (
        profitability["gross_profit"]["amount_cents"]
    )

    operating_expenses_cents = (
        profitability["operating_expenses"]["amount_cents"]
    )

    operating_result_cents = (
        profitability["operating_result"]["amount_cents"]
    )

    total_expenses_cents = expenses["total_expenses_cents"]

    total_budget_cents = (
        budgets["summary"]["total_budget_cents"]
    )

    budget_actual_expenses_cents = (
        budgets["summary"]["total_actual_expenses_cents"]
    )

    budget_variance_cents = (
        budgets["summary"]["total_variance_cents"]
    )

    # Calculate additional financial indicators.
    gross_margin_percentage = _percentage(
        gross_profit_cents,
        net_revenue_cents,
    )

    operating_margin_percentage = _percentage(
        operating_result_cents,
        net_revenue_cents,
    )

    cogs_percentage = _percentage(
        net_cogs_cents,
        net_revenue_cents,
    )

    operating_expense_ratio = _percentage(
        operating_expenses_cents,
        net_revenue_cents,
    )

    sales_return_rate = _percentage(
        sales_returns_cents,
        gross_revenue_cents,
    )

    budget_utilisation_percentage = _percentage(
        budget_actual_expenses_cents,
        total_budget_cents,
    )

    average_net_revenue_per_order_cents = (
        round(net_revenue_cents / revenue["completed_orders"])
        if revenue["completed_orders"] > 0
        else None
    )

    # Estimate the net revenue required to break even.
    # This assumes the current gross margin remains constant
    # and operating expenses do not increase.
    if gross_profit_cents > 0 and net_revenue_cents > 0:
        break_even_revenue_cents = round(
            operating_expenses_cents
            / (gross_profit_cents / net_revenue_cents)
        )

        additional_revenue_needed_cents = max(
            0,
            break_even_revenue_cents - net_revenue_cents,
        )
    else:
        break_even_revenue_cents = None
        additional_revenue_needed_cents = None

    gross_profit_gap_cents = max(
        0,
        operating_expenses_cents - gross_profit_cents,
    )

    # Check consistency between independently exposed services.
    reconciliation = {
        "revenue_matches_profitability": (
            net_revenue_cents
            == profitability["revenue"]["net_revenue_cents"]
        ),
        "expenses_match_profitability": (
            total_expenses_cents == operating_expenses_cents
        ),
        "budget_actuals_match_expenses": (
            budget_actual_expenses_cents == total_expenses_cents
        ),
        "expense_monthly_trend_reconciles": (
            expenses["monthly_reconciliation"]["reconciles"]
        ),
        "all_checks_passed": False,
    }

    reconciliation["all_checks_passed"] = all(
        value
        for key, value in reconciliation.items()
        if key != "all_checks_passed"
    )

    currency = revenue["currency"]

    if not all(
        result["currency"] == currency
        for result in services.values()
    ):
        raise ValueError(
            "Financial services returned inconsistent currencies."
        )

    return {
        "dataset_version_id": dataset_version_id,
        "period": revenue["period"],
        "currency": currency,

        "kpis": {
            "gross_revenue": _money(gross_revenue_cents),
            "sales_returns": _money(sales_returns_cents),
            "net_revenue": _money(net_revenue_cents),
            "cost_of_goods_sold": _money(net_cogs_cents),
            "gross_profit": _money(gross_profit_cents),
            "operating_expenses": _money(operating_expenses_cents),
            "operating_result": _money(operating_result_cents),
            "gross_profit_gap": _money(gross_profit_gap_cents),
            "total_budget": _money(total_budget_cents),
            "budget_actual_expenses": _money(
                budget_actual_expenses_cents
            ),
            "budget_variance": _money(budget_variance_cents),
            "total_cash_inflows": _money(
                cash_flow["total_inflows_cents"]
            ),
            "total_cash_outflows": _money(
                cash_flow["total_outflows_cents"]
            ),
            "net_cash_movement": _money(
                cash_flow["net_cash_movement_cents"]
            ),

            "gross_margin_percentage": gross_margin_percentage,
            "operating_margin_percentage": operating_margin_percentage,
            "cogs_percentage_of_net_revenue": cogs_percentage,
            "operating_expense_percentage": operating_expense_ratio,
            "sales_return_rate_percentage": sales_return_rate,
            "budget_utilisation_percentage": (
                budget_utilisation_percentage
            ),

            "completed_orders": revenue["completed_orders"],
            "completed_returns": revenue["completed_returns"],
            "expense_count": expenses["expense_count"],

            "average_net_revenue_per_order": (
                _money(average_net_revenue_per_order_cents)
                if average_net_revenue_per_order_cents is not None
                else None
            ),

            "break_even_net_revenue_estimate": (
                _money(break_even_revenue_cents)
                if break_even_revenue_cents is not None
                else None
            ),

            "additional_net_revenue_needed_for_break_even": (
                _money(additional_revenue_needed_cents)
                if additional_revenue_needed_cents is not None
                else None
            ),
        },

        "performance": {
            "gross_profit_status": (
                "positive" if gross_profit_cents > 0
                else "negative" if gross_profit_cents < 0
                else "break_even"
            ),
            "operating_status": profitability["operating_result"]["status"],
            "budget_status": budgets["summary"]["performance"],
        },

        "expense_breakdown": {
            "by_category": expenses["by_category"],
            "by_department": expenses["by_department"],
            "by_store": expenses["by_store"],
            "monthly_trend": expenses["monthly_trend"],
        },

        "budget_analysis": {
            "summary": budgets["summary"],
            "by_category": budgets["by_category"],
            "allocation_basis": budgets["allocation_basis"],
            "limitations": budgets["limitations"],
        },

        "cash_flow_analysis": {
            "customer_collections": cash_flow["customer_collections"],
            "customer_refunds": cash_flow["customer_refunds"],
            "expense_payments": cash_flow["expense_payments"],
            "supplier_payments": cash_flow["supplier_payments"],
            "monthly_trend": cash_flow["monthly_trend"],
            "coverage": cash_flow["cash_flow_coverage"],
        },

        "reconciliation": reconciliation,
    }
