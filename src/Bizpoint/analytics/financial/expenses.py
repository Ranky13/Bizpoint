from datetime import date
from typing import Any

from Bizpoint.analytics.common.query import execute_query


def get_expense_metrics(
    dataset_version_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """
    Calculate approved operating expense metrics.

    Expenses are recognised by expense_date.
    Only approved expenses are included.
    Expense payments are not treated as expenses.
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

    date_filter = """
        AND (
            CAST(:start_date AS DATE) IS NULL
            OR e.expense_date >= CAST(:start_date AS DATE)
        )
        AND (
            CAST(:end_date AS DATE) IS NULL
            OR e.expense_date < CAST(:end_date AS DATE) + INTERVAL '1 day'
        )
    """

    summary_query = """
        SELECT
            COALESCE(SUM(e.amount_cents), 0) AS total_expenses_cents,
            COUNT(*) AS expense_count
        FROM expenses AS e
        WHERE e.dataset_version_id = :dataset_version_id
          AND e.status = 'approved'
          AND (
              CAST(:start_date AS DATE) IS NULL
              OR e.expense_date >= CAST(:start_date AS DATE)
          )
          AND (
              CAST(:end_date AS DATE) IS NULL
              OR e.expense_date < CAST(:end_date AS DATE) + INTERVAL '1 day'
          )
    """

    category_query = f"""
        SELECT
            COALESCE(ec.category_name, 'Uncategorised') AS category,
            SUM(e.amount_cents) AS amount_cents,
            COUNT(e.id) AS expense_count
        FROM expenses AS e
        LEFT JOIN expense_categories AS ec
            ON ec.id = e.expense_category_id
           AND ec.dataset_version_id = e.dataset_version_id
        WHERE e.dataset_version_id = :dataset_version_id
          AND e.status = 'approved'
          {date_filter}
        GROUP BY ec.category_name
        ORDER BY amount_cents DESC
    """

    department_query = f"""
        SELECT
            COALESCE(d.department_name, 'Unassigned') AS department,
            SUM(e.amount_cents) AS amount_cents,
            COUNT(e.id) AS expense_count
        FROM expenses AS e
        LEFT JOIN departments AS d
            ON d.id = e.department_id
           AND d.dataset_version_id = e.dataset_version_id
        WHERE e.dataset_version_id = :dataset_version_id
          AND e.status = 'approved'
          {date_filter}
        GROUP BY d.department_name
        ORDER BY amount_cents DESC
    """

    store_query = f"""
        SELECT
            COALESCE(s.store_name, 'Unassigned') AS store,
            SUM(e.amount_cents) AS amount_cents,
            COUNT(e.id) AS expense_count
        FROM expenses AS e
        LEFT JOIN stores AS s
            ON s.id = e.store_id
           AND s.dataset_version_id = e.dataset_version_id
        WHERE e.dataset_version_id = :dataset_version_id
          AND e.status = 'approved'
          {date_filter}
        GROUP BY s.store_name
        ORDER BY amount_cents DESC
    """

    monthly_query = """
        SELECT
            DATE_TRUNC('month', e.expense_date)::DATE AS month,
            SUM(e.amount_cents) AS amount_cents,
            COUNT(*) AS expense_count
        FROM expenses AS e
        WHERE e.dataset_version_id = :dataset_version_id
          AND e.status = 'approved'
          AND (
              CAST(:start_date AS DATE) IS NULL
              OR e.expense_date >= CAST(:start_date AS DATE)
          )
          AND (
              CAST(:end_date AS DATE) IS NULL
              OR e.expense_date < CAST(:end_date AS DATE) + INTERVAL '1 day'
          )
        GROUP BY DATE_TRUNC('month', e.expense_date)
        ORDER BY month
    """

    summary = execute_query(summary_query, parameters)[0]
    categories = execute_query(category_query, parameters)
    departments = execute_query(department_query, parameters)
    stores = execute_query(store_query, parameters)
    monthly = execute_query(monthly_query, parameters)

    total_expenses_cents = int(summary["total_expenses_cents"])

    def format_breakdown(
        rows: list[dict[str, Any]],
        label: str,
    ) -> dict[str, Any]:

        results = []

        for row in rows:
            amount_cents = int(row["amount_cents"])

            results.append({
                label: row[label],
                "amount_cents": amount_cents,
                "amount": round(amount_cents / 100, 2),
                "expense_count": int(row["expense_count"]),
                "percentage": (
                    round(amount_cents / total_expenses_cents * 100, 2)
                    if total_expenses_cents else 0.0
                ),
            })

        breakdown_total = sum(
            item["amount_cents"] for item in results
        )

        return {
            "items": results,
            "total_cents": breakdown_total,
            "total": round(breakdown_total / 100, 2),
            "reconciles": breakdown_total == total_expenses_cents,
        }

    monthly_results = []

    for row in monthly:
        amount_cents = int(row["amount_cents"])

        monthly_results.append({
            "month": row["month"].isoformat(),
            "amount_cents": amount_cents,
            "amount": round(amount_cents / 100, 2),
            "expense_count": int(row["expense_count"]),
        })

    monthly_total_cents = sum(
        item["amount_cents"] for item in monthly_results
    )

    return {
        "dataset_version_id": dataset_version_id,
        "period": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },
        "expense_count": int(summary["expense_count"]),
        "total_expenses_cents": total_expenses_cents,
        "total_expenses": round(total_expenses_cents / 100, 2),
        "by_category": format_breakdown(categories, "category"),
        "by_department": format_breakdown(departments, "department"),
        "by_store": format_breakdown(stores, "store"),
        "monthly_trend": monthly_results,
        "monthly_reconciliation": {
            "total_cents": monthly_total_cents,
            "reconciles": monthly_total_cents == total_expenses_cents,
        },
        "currency": "USD",
    }
