from datetime import date
from typing import Any

from Bizpoint.analytics.common.query import execute_query


def get_budget_metrics(
    dataset_version_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """
    Calculate historical budget-versus-actual performance.

    Budget scope:
        Closed budgets only.

    Actual expenditure:
        Approved expenses recognised by expense_date.

    Allocation:
        Expense category and overlapping budget period.

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

    budget_query = """
        WITH selected_budgets AS (
            SELECT
                b.id AS budget_id,
                b.budget_code,
                b.budget_name,
                b.expense_category_id,
                ec.category_name,
                b.budget_amount_cents,
                b.start_date::DATE AS start_date,
                b.end_date::DATE AS end_date,
                b.status
            FROM budgets AS b
            INNER JOIN expense_categories AS ec
                ON ec.id = b.expense_category_id
               AND ec.dataset_version_id = b.dataset_version_id
            WHERE b.dataset_version_id = :dataset_version_id
              AND b.status = 'closed'
              AND (
                  CAST(:start_date AS DATE) IS NULL
                  OR b.end_date::DATE >= CAST(:start_date AS DATE)
              )
              AND (
                  CAST(:end_date AS DATE) IS NULL
                  OR b.start_date::DATE <= CAST(:end_date AS DATE)
              )
        ),

        budget_actuals AS (
            SELECT
                b.budget_id,
                b.budget_code,
                b.budget_name,
                b.category_name,
                b.budget_amount_cents,
                b.start_date,
                b.end_date,

                COALESCE(SUM(e.amount_cents), 0)
                    AS actual_expenses_cents,

                COUNT(e.id) AS expense_count

            FROM selected_budgets AS b

            LEFT JOIN expenses AS e
                ON e.dataset_version_id = :dataset_version_id
               AND e.expense_category_id = b.expense_category_id
               AND e.status = 'approved'
               AND e.expense_date >= b.start_date
               AND e.expense_date < b.end_date

            GROUP BY
                b.budget_id,
                b.budget_code,
                b.budget_name,
                b.category_name,
                b.budget_amount_cents,
                b.start_date,
                b.end_date
        )

        SELECT *
        FROM budget_actuals
        ORDER BY start_date, category_name
    """

    rows = execute_query(budget_query, parameters)

    budget_records = []
    category_totals: dict[str, dict[str, Any]] = {}

    total_budget_cents = 0
    total_actual_cents = 0
    total_expense_count = 0

    for row in rows:
        budget_cents = int(row["budget_amount_cents"])
        actual_cents = int(row["actual_expenses_cents"])
        expense_count = int(row["expense_count"])

        variance_cents = budget_cents - actual_cents

        utilisation = (
            round(actual_cents / budget_cents * 100, 2)
            if budget_cents else None
        )

        record = {
            "budget_code": row["budget_code"],
            "budget_name": row["budget_name"],
            "category": row["category_name"],
            "period": {
                "start_date": row["start_date"].isoformat(),
                "end_date": row["end_date"].isoformat(),
            },
            "budget_amount_cents": budget_cents,
            "actual_expenses_cents": actual_cents,
            "variance_cents": variance_cents,
            "budget_amount": round(budget_cents / 100, 2),
            "actual_expenses": round(actual_cents / 100, 2),
            "variance": round(variance_cents / 100, 2),
            "utilisation_percentage": utilisation,
            "expense_count": expense_count,
            "performance": (
                "overspent" if variance_cents < 0
                else "underspent" if variance_cents > 0
                else "on_budget"
            ),
        }

        budget_records.append(record)

        total_budget_cents += budget_cents
        total_actual_cents += actual_cents
        total_expense_count += expense_count

        category = row["category_name"]

        if category not in category_totals:
            category_totals[category] = {
                "budget_cents": 0,
                "actual_cents": 0,
                "expense_count": 0,
                "budget_count": 0,
            }

        category_totals[category]["budget_cents"] += budget_cents
        category_totals[category]["actual_cents"] += actual_cents
        category_totals[category]["expense_count"] += expense_count
        category_totals[category]["budget_count"] += 1

    category_results = []

    for category, values in category_totals.items():
        budget_cents = values["budget_cents"]
        actual_cents = values["actual_cents"]
        variance_cents = budget_cents - actual_cents

        category_results.append({
            "category": category,
            "budget_count": values["budget_count"],
            "budget_amount_cents": budget_cents,
            "actual_expenses_cents": actual_cents,
            "variance_cents": variance_cents,
            "budget_amount": round(budget_cents / 100, 2),
            "actual_expenses": round(actual_cents / 100, 2),
            "variance": round(variance_cents / 100, 2),
            "utilisation_percentage": (
                round(actual_cents / budget_cents * 100, 2)
                if budget_cents else None
            ),
            "expense_count": values["expense_count"],
            "performance": (
                "overspent" if variance_cents < 0
                else "underspent" if variance_cents > 0
                else "on_budget"
            ),
        })

    category_results.sort(
        key=lambda item: item["actual_expenses_cents"],
        reverse=True,
    )

    total_variance_cents = total_budget_cents - total_actual_cents

    return {
        "dataset_version_id": dataset_version_id,

        "period": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },

        "summary": {
            "budget_count": len(budget_records),
            "expense_count": total_expense_count,
            "total_budget_cents": total_budget_cents,
            "total_actual_expenses_cents": total_actual_cents,
            "total_variance_cents": total_variance_cents,
            "total_budget": round(total_budget_cents / 100, 2),
            "total_actual_expenses": round(total_actual_cents / 100, 2),
            "total_variance": round(total_variance_cents / 100, 2),
            "utilisation_percentage": (
                round(total_actual_cents / total_budget_cents * 100, 2)
                if total_budget_cents else None
            ),
            "performance": (
                "overspent" if total_variance_cents < 0
                else "underspent" if total_variance_cents > 0
                else "on_budget"
            ),
        },

        "by_category": category_results,
        "budgets": budget_records,

        "allocation_basis": [
            "dataset_version_id",
            "expense_category_id",
            "expense_date",
        ],

        "limitations": [
            "Only closed budgets are included.",
            "Budgets have no department or store assignments.",
            "Only approved expenses are included.",
            "Actual expenses outside budget periods are not allocated.",
            "This is historical synthetic budget analysis, not an independent forecast.",
        ],

        "currency": "USD",
    }

