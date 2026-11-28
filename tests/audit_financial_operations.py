
from sqlalchemy import text

from Bizpoint.database.connection import engine
from Bizpoint.data_generation.config import DATASET_NAME


DATASET_VERSION_ID = "b580a1d713b1425685bbc624ef8473b6"


def scalar(connection, query, params=None):
    result = connection.execute(text(query), params or {})
    return result.scalar() or 0


def count_check(connection, title, query, params=None):
    count = scalar(connection, query, params)
    status = "PASS" if count == 0 else "FAIL"
    print(f"{title}: {status} ({count})")
    return count


def main():
    print("=" * 65)
    print("BIZPOINT FINANCIAL OPERATIONS AUDIT")
    print("=" * 65)

    params = {"dataset_version_id": DATASET_VERSION_ID}
    failures = {}

    with engine.connect() as connection:

        print(f"Dataset: {DATASET_NAME}")
        print(f"Dataset version: {DATASET_VERSION_ID}")

        # ---------------------------------------------------------
        # RECORD COUNTS
        # ---------------------------------------------------------

        tables = {
            "Expenses": "expenses",
            "Expense categories": "expense_categories",
            "Financial accounts": "financial_accounts",
            "Expense payments": "expense_payments",
            "Budgets": "budgets",
            "Marketing campaigns": "marketing_campaigns",
            "Campaign costs": "campaign_costs",
            "Campaign attributions": "campaign_attributions",
        }

        print("\nFINANCIAL OPERATIONS RECORD COUNTS")
        print("-" * 65)

        for label, table in tables.items():
            total = scalar(
                connection,
                f"""
                SELECT COUNT(*)
                FROM {table}
                WHERE dataset_version_id = :dataset_version_id
                """,
                params,
            )
            print(f"{label}: {total:,}")

        # ---------------------------------------------------------
        # EXPENSE VALIDATION
        # ---------------------------------------------------------

        print("\nEXPENSE INTEGRITY CHECKS")
        print("-" * 65)

        failures["invalid expense amounts"] = count_check(
            connection,
            "1. Invalid expense amounts",
            """
            SELECT COUNT(*)
            FROM expenses
            WHERE dataset_version_id = :dataset_version_id
              AND amount_cents <= 0
            """,
            params,
        )

        failures["invalid expense statuses"] = count_check(
            connection,
            "2. Invalid expense statuses",
            """
            SELECT COUNT(*)
            FROM expenses
            WHERE dataset_version_id = :dataset_version_id
              AND status NOT IN (
                  'draft', 'approved', 'rejected', 'cancelled'
              )
            """,
            params,
        )

        failures["missing expense categories"] = count_check(
            connection,
            "3. Missing or invalid expense categories",
            """
            SELECT COUNT(*)
            FROM expenses e
            LEFT JOIN expense_categories c
              ON c.id = e.expense_category_id
             AND c.dataset_version_id = e.dataset_version_id
            WHERE e.dataset_version_id = :dataset_version_id
              AND (
                  e.expense_category_id IS NULL
                  OR c.id IS NULL
              )
            """,
            params,
        )

        failures["invalid expense departments"] = count_check(
            connection,
            "4. Invalid expense department references",
            """
            SELECT COUNT(*)
            FROM expenses e
            LEFT JOIN departments d
              ON d.id = e.department_id
             AND d.dataset_version_id = e.dataset_version_id
            WHERE e.dataset_version_id = :dataset_version_id
              AND e.department_id IS NOT NULL
              AND d.id IS NULL
            """,
            params,
        )

        failures["invalid expense stores"] = count_check(
            connection,
            "5. Invalid expense store references",
            """
            SELECT COUNT(*)
            FROM expenses e
            LEFT JOIN stores s
              ON s.id = e.store_id
             AND s.dataset_version_id = e.dataset_version_id
            WHERE e.dataset_version_id = :dataset_version_id
              AND e.store_id IS NOT NULL
              AND s.id IS NULL
            """,
            params,
        )

        # ---------------------------------------------------------
        # EXPENSE PAYMENT VALIDATION
        # ---------------------------------------------------------

        print("\nEXPENSE PAYMENT INTEGRITY CHECKS")
        print("-" * 65)

        failures["invalid expense payment amounts"] = count_check(
            connection,
            "6. Invalid expense payment amounts",
            """
            SELECT COUNT(*)
            FROM expense_payments
            WHERE dataset_version_id = :dataset_version_id
              AND amount_cents <= 0
            """,
            params,
        )

        failures["invalid expense payment statuses"] = count_check(
            connection,
            "7. Invalid expense payment statuses",
            """
            SELECT COUNT(*)
            FROM expense_payments
            WHERE dataset_version_id = :dataset_version_id
              AND status NOT IN (
                  'pending', 'successful', 'failed', 'reversed'
              )
            """,
            params,
        )

        failures["invalid expense payment links"] = count_check(
            connection,
            "8. Invalid expense payment expense references",
            """
            SELECT COUNT(*)
            FROM expense_payments ep
            LEFT JOIN expenses e
              ON e.id = ep.expense_id
             AND e.dataset_version_id = ep.dataset_version_id
            WHERE ep.dataset_version_id = :dataset_version_id
              AND (
                  e.id IS NULL
                  OR e.status <> 'approved'
              )
            """,
            params,
        )

        failures["invalid expense payment accounts"] = count_check(
            connection,
            "9. Invalid expense payment financial accounts",
            """
            SELECT COUNT(*)
            FROM expense_payments ep
            LEFT JOIN financial_accounts fa
              ON fa.id = ep.financial_account_id
             AND fa.dataset_version_id = ep.dataset_version_id
            WHERE ep.dataset_version_id = :dataset_version_id
              AND fa.id IS NULL
            """,
            params,
        )

        failures["duplicate expense payments"] = count_check(
            connection,
            "10. Duplicate payments for the same expense",
            """
            SELECT COUNT(*)
            FROM (
                SELECT expense_id
                FROM expense_payments
                WHERE dataset_version_id = :dataset_version_id
                GROUP BY expense_id
                HAVING COUNT(*) > 1
            ) duplicates
            """,
            params,
        )

        failures["successful payments exceeding expenses"] = count_check(
            connection,
            "11. Successful payments exceeding expense amounts",
            """
            SELECT COUNT(*)
            FROM (
                SELECT
                    e.id,
                    e.amount_cents,
                    SUM(ep.amount_cents) AS paid_amount
                FROM expenses e
                JOIN expense_payments ep
                  ON ep.expense_id = e.id
                 AND ep.dataset_version_id = e.dataset_version_id
                WHERE e.dataset_version_id = :dataset_version_id
                  AND ep.status = 'successful'
                GROUP BY e.id, e.amount_cents
                HAVING SUM(ep.amount_cents) > e.amount_cents
            ) payment_totals
            """,
            params,
        )

        # ---------------------------------------------------------
        # BUDGET VALIDATION
        # ---------------------------------------------------------

        print("\nBUDGET INTEGRITY CHECKS")
        print("-" * 65)

        failures["invalid budget amounts"] = count_check(
            connection,
            "12. Invalid budget amounts",
            """
            SELECT COUNT(*)
            FROM budgets
            WHERE dataset_version_id = :dataset_version_id
              AND budget_amount_cents <= 0
            """,
            params,
        )

        failures["invalid budget dates"] = count_check(
            connection,
            "13. Invalid budget date ranges",
            """
            SELECT COUNT(*)
            FROM budgets
            WHERE dataset_version_id = :dataset_version_id
              AND start_date > end_date
            """,
            params,
        )

        failures["invalid budget statuses"] = count_check(
            connection,
            "14. Invalid budget statuses",
            """
            SELECT COUNT(*)
            FROM budgets
            WHERE dataset_version_id = :dataset_version_id
              AND status NOT IN (
                  'draft', 'approved', 'closed', 'cancelled'
              )
            """,
            params,
        )

        failures["invalid budget categories"] = count_check(
            connection,
            "15. Invalid budget expense category references",
            """
            SELECT COUNT(*)
            FROM budgets b
            LEFT JOIN expense_categories c
              ON c.id = b.expense_category_id
             AND c.dataset_version_id = b.dataset_version_id
            WHERE b.dataset_version_id = :dataset_version_id
              AND b.expense_category_id IS NOT NULL
              AND c.id IS NULL
            """,
            params,
        )

        failures["invalid budget departments"] = count_check(
            connection,
            "16. Invalid budget department references",
            """
            SELECT COUNT(*)
            FROM budgets b
            LEFT JOIN departments d
              ON d.id = b.department_id
             AND d.dataset_version_id = b.dataset_version_id
            WHERE b.dataset_version_id = :dataset_version_id
              AND b.department_id IS NOT NULL
              AND d.id IS NULL
            """,
            params,
        )

        failures["invalid budget stores"] = count_check(
            connection,
            "17. Invalid budget store references",
            """
            SELECT COUNT(*)
            FROM budgets b
            LEFT JOIN stores s
              ON s.id = b.store_id
             AND s.dataset_version_id = b.dataset_version_id
            WHERE b.dataset_version_id = :dataset_version_id
              AND b.store_id IS NOT NULL
              AND s.id IS NULL
            """,
            params,
        )

        # ---------------------------------------------------------
        # MARKETING CAMPAIGN VALIDATION
        # ---------------------------------------------------------

        print("\nMARKETING CAMPAIGN INTEGRITY CHECKS")
        print("-" * 65)

        failures["invalid campaign statuses"] = count_check(
            connection,
            "18. Invalid campaign statuses",
            """
            SELECT COUNT(*)
            FROM marketing_campaigns
            WHERE dataset_version_id = :dataset_version_id
              AND status NOT IN (
                  'draft', 'planned', 'active', 'completed', 'cancelled'
              )
            """,
            params,
        )

        failures["invalid campaign dates"] = count_check(
            connection,
            "19. Invalid campaign date ranges",
            """
            SELECT COUNT(*)
            FROM marketing_campaigns
            WHERE dataset_version_id = :dataset_version_id
              AND start_date > end_date
            """,
            params,
        )

        # ---------------------------------------------------------
        # CAMPAIGN COST VALIDATION
        # ---------------------------------------------------------

        print("\nCAMPAIGN COST RECONCILIATION")
        print("-" * 65)

        failures["invalid campaign cost amounts"] = count_check(
            connection,
            "20. Invalid campaign cost amounts",
            """
            SELECT COUNT(*)
            FROM campaign_costs
            WHERE dataset_version_id = :dataset_version_id
              AND amount_cents <= 0
            """,
            params,
        )

        failures["invalid campaign cost campaign links"] = count_check(
            connection,
            "21. Invalid campaign references in campaign costs",
            """
            SELECT COUNT(*)
            FROM campaign_costs cc
            LEFT JOIN marketing_campaigns mc
              ON mc.id = cc.campaign_id
             AND mc.dataset_version_id = cc.dataset_version_id
            WHERE cc.dataset_version_id = :dataset_version_id
              AND mc.id IS NULL
            """,
            params,
        )

        failures["invalid campaign cost expense links"] = count_check(
            connection,
            "22. Invalid linked expense references",
            """
            SELECT COUNT(*)
            FROM campaign_costs cc
            LEFT JOIN expenses e
              ON e.id = cc.expense_id
             AND e.dataset_version_id = cc.dataset_version_id
            WHERE cc.dataset_version_id = :dataset_version_id
              AND cc.expense_id IS NOT NULL
              AND (
                  e.id IS NULL
                  OR e.status <> 'approved'
              )
            """,
            params,
        )

        failures["campaign costs exceeding expenses"] = count_check(
            connection,
            "23. Campaign allocations exceeding expense amounts",
            """
            SELECT COUNT(*)
            FROM (
                SELECT
                    e.id,
                    e.amount_cents,
                    SUM(cc.amount_cents) AS allocated_amount
                FROM expenses e
                JOIN campaign_costs cc
                  ON cc.expense_id = e.id
                 AND cc.dataset_version_id = e.dataset_version_id
                WHERE e.dataset_version_id = :dataset_version_id
                  AND cc.expense_id IS NOT NULL
                GROUP BY e.id, e.amount_cents
                HAVING SUM(cc.amount_cents) > e.amount_cents
            ) allocations
            """,
            params,
        )

        # ---------------------------------------------------------
        # CAMPAIGN ATTRIBUTION VALIDATION
        # ---------------------------------------------------------

        print("\nCAMPAIGN ATTRIBUTION INTEGRITY CHECKS")
        print("-" * 65)

        failures["invalid attribution campaign links"] = count_check(
            connection,
            "24. Invalid attribution campaign references",
            """
            SELECT COUNT(*)
            FROM campaign_attributions ca
            LEFT JOIN marketing_campaigns mc
              ON mc.id = ca.campaign_id
             AND mc.dataset_version_id = ca.dataset_version_id
            WHERE ca.dataset_version_id = :dataset_version_id
              AND mc.id IS NULL
            """,
            params,
        )

        failures["invalid attribution sales links"] = count_check(
            connection,
            "25. Invalid attribution sales order references",
            """
            SELECT COUNT(*)
            FROM campaign_attributions ca
            LEFT JOIN sales_orders so
              ON so.id = ca.sales_order_id
             AND so.dataset_version_id = ca.dataset_version_id
            WHERE ca.dataset_version_id = :dataset_version_id
              AND (
                  so.id IS NULL
                  OR so.status <> 'completed'
              )
            """,
            params,
        )

        failures["invalid attribution models"] = count_check(
            connection,
            "26. Invalid attribution models",
            """
            SELECT COUNT(*)
            FROM campaign_attributions
            WHERE dataset_version_id = :dataset_version_id
              AND attribution_model NOT IN (
                  'first_touch', 'last_touch', 'linear', 'position_based'
              )
            """,
            params,
        )

        # Correct database column name:
        # attribution_weight_basis_points

        failures["invalid attribution weights"] = count_check(
            connection,
            "27. Invalid attribution weights",
            """
            SELECT COUNT(*)
            FROM campaign_attributions
            WHERE dataset_version_id = :dataset_version_id
              AND (
                  attribution_weight_basis_points <= 0
                  OR attribution_weight_basis_points > 10000
              )
            """,
            params,
        )

        failures["duplicate campaign order attributions"] = count_check(
            connection,
            "28. Duplicate campaign / sales order attributions",
            """
            SELECT COUNT(*)
            FROM (
                SELECT campaign_id, sales_order_id
                FROM campaign_attributions
                WHERE dataset_version_id = :dataset_version_id
                GROUP BY campaign_id, sales_order_id
                HAVING COUNT(*) > 1
            ) duplicates
            """,
            params,
        )

        # ---------------------------------------------------------
        # FINANCIAL SUMMARY
        # ---------------------------------------------------------

        print("\nFINANCIAL OPERATIONS SUMMARY")
        print("-" * 65)

        expense_totals = connection.execute(
            text(
                """
                SELECT
                    COUNT(*) AS expense_count,
                    COALESCE(SUM(amount_cents), 0) AS total_expenses,
                    COALESCE(
                        SUM(
                            CASE
                                WHEN status = 'approved'
                                THEN amount_cents
                                ELSE 0
                            END
                        ), 0
                    ) AS approved_expenses
                FROM expenses
                WHERE dataset_version_id = :dataset_version_id
                """
            ),
            params,
        ).one()

        payment_totals = connection.execute(
            text(
                """
                SELECT
                    COUNT(*) AS payment_count,
                    COALESCE(
                        SUM(
                            CASE
                                WHEN status = 'successful'
                                THEN amount_cents
                                ELSE 0
                            END
                        ), 0
                    ) AS successful_payments
                FROM expense_payments
                WHERE dataset_version_id = :dataset_version_id
                """
            ),
            params,
        ).one()

        campaign_totals = connection.execute(
            text(
                """
                SELECT
                    COUNT(*) AS cost_count,
                    COALESCE(SUM(amount_cents), 0) AS campaign_costs
                FROM campaign_costs
                WHERE dataset_version_id = :dataset_version_id
                """
            ),
            params,
        ).one()

        print(f"Expense records: {expense_totals.expense_count:,}")
        print(
            f"Total recorded expenses: "
            f"${expense_totals.total_expenses / 100:,.2f}"
        )
        print(
            f"Approved expenses: "
            f"${expense_totals.approved_expenses / 100:,.2f}"
        )

        print(f"Expense payment records: {payment_totals.payment_count:,}")
        print(
            f"Successful expense payments: "
            f"${payment_totals.successful_payments / 100:,.2f}"
        )

        print(f"Campaign cost records: {campaign_totals.cost_count:,}")
        print(
            f"Recorded campaign costs: "
            f"${campaign_totals.campaign_costs / 100:,.2f}"
        )

    # -------------------------------------------------------------
    # FINAL RESULT
    # -------------------------------------------------------------

    print("\n" + "=" * 65)
    print("FINANCIAL OPERATIONS AUDIT SUMMARY")
    print("=" * 65)

    for check_name, issue_count in failures.items():
        status = "PASS" if issue_count == 0 else "FAIL"
        print(f"{check_name}: {status} ({issue_count})")

    total_issues = sum(failures.values())

    print("-" * 65)

    if total_issues == 0:
        print("RESULT: FINANCIAL OPERATIONS AUDIT PASSED")
    else:
        print(f"RESULT: AUDIT FOUND {total_issues} ISSUE(S)")

    print("=" * 65)


if __name__ == "__main__":
    main()
