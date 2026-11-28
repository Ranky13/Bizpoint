
from sqlalchemy import text

from Bizpoint.database.connection import engine


DATASET_VERSION_ID = "b580a1d713b1425685bbc624ef8473b6"
EXPECTED_VAT_RATE_BPS = 750

audit_results = []


def money(cents):
    return f"${cents / 100:,.2f}"


def check(name, passed, detail=""):
    audit_results.append((name, passed))

    status = "PASSED" if passed else "FAILED"

    print(f"[{status}] {name}")

    if detail:
        print(f"         {detail}")


def scalar(connection, query, params=None):
    result = connection.execute(
        text(query),
        params or {}
    )
    return result.scalar() or 0


def print_section(title):
    print("\n" + "=" * 65)
    print(title)
    print("=" * 65)


with engine.connect() as connection:

    params = {"version_id": DATASET_VERSION_ID}

    # ---------------------------------------------------------
    # 1. SALES REVENUE
    # ---------------------------------------------------------

    print_section("1. SALES REVENUE RECONCILIATION")

    sales = connection.execute(
        text("""
            SELECT
                COUNT(*) AS order_count,
                COALESCE(SUM(total_amount_cents), 0)
                    AS revenue_cents
            FROM sales_orders
            WHERE dataset_version_id = :version_id
              AND status = 'completed'
        """),
        params
    ).one()

    completed_orders = sales.order_count
    gross_revenue = sales.revenue_cents

    item_revenue = scalar(
        connection,
        """
        SELECT COALESCE(
            SUM(
                (quantity * original_unit_price_cents)
                - discount_amount_cents
            ), 0
        )
        FROM sales_order_items
        WHERE dataset_version_id = :version_id
          AND order_id IN (
              SELECT id
              FROM sales_orders
              WHERE dataset_version_id = :version_id
                AND status = 'completed'
          )
        """,
        params
    )

    print(f"Completed sales orders: {completed_orders:,}")
    print(f"Recognized gross revenue: {money(gross_revenue)}")
    print(f"Calculated item revenue: {money(item_revenue)}")

    check(
        "Completed sales order totals match item totals",
        gross_revenue == item_revenue,
        f"Difference: {money(gross_revenue - item_revenue)}"
    )

    # ---------------------------------------------------------
    # 2. VAT RECONCILIATION
    # ---------------------------------------------------------

    print_section("2. VAT RECONCILIATION")

    vat = connection.execute(
        text("""
            SELECT
                COUNT(*) AS tax_record_count,
                COALESCE(SUM(taxable_amount_cents), 0)
                    AS taxable_base_cents,
                COALESCE(SUM(tax_amount_cents), 0)
                    AS vat_amount_cents,
                COUNT(*) FILTER (
                    WHERE tax_rate_basis_points != :vat_rate
                ) AS incorrect_rate_count
            FROM sales_order_item_taxes
            WHERE dataset_version_id = :version_id
        """),
        {
            "version_id": DATASET_VERSION_ID,
            "vat_rate": EXPECTED_VAT_RATE_BPS
        }
    ).one()

    print(f"VAT records: {vat.tax_record_count:,}")
    print(f"Taxable sales base: {money(vat.taxable_base_cents)}")
    print(f"Calculated VAT: {money(vat.vat_amount_cents)}")
    print("Expected VAT rate: 7.5%")

    check(
        "VAT rate is consistently 7.5%",
        vat.incorrect_rate_count == 0,
        f"Incorrect-rate records: {vat.incorrect_rate_count}"
    )

    check(
        "VAT taxable base matches completed sales revenue",
        vat.taxable_base_cents == gross_revenue,
        f"Difference: {money(vat.taxable_base_cents - gross_revenue)}"
    )

    # VAT remains separate from recognized revenue.
    print("Note: VAT is reported separately and is not added to revenue.")

    # ---------------------------------------------------------
    # 3. SALES RETURNS
    # ---------------------------------------------------------

    print_section("3. SALES RETURNS RECONCILIATION")

    returns = connection.execute(
        text("""
            SELECT
                COUNT(*) FILTER (
                    WHERE status = 'completed'
                ) AS completed_count,

                COUNT(*) FILTER (
                    WHERE status = 'approved'
                ) AS approved_count,

                COUNT(*) FILTER (
                    WHERE status = 'requested'
                ) AS requested_count,

                COUNT(*) FILTER (
                    WHERE status = 'rejected'
                ) AS rejected_count

            FROM sales_returns
            WHERE dataset_version_id = :version_id
        """),
        params
    ).one()

    completed_return_amount = scalar(
        connection,
        """
        SELECT COALESCE(SUM(ri.return_amount_cents), 0)
        FROM sales_return_items ri
        JOIN sales_returns r
          ON r.id = ri.return_id
        WHERE r.dataset_version_id = :version_id
          AND ri.dataset_version_id = :version_id
          AND r.status = 'completed'
        """,
        params
    )

    print(f"Completed returns: {returns.completed_count}")
    print(f"Approved returns: {returns.approved_count}")
    print(f"Requested returns: {returns.requested_count}")
    print(f"Rejected returns: {returns.rejected_count}")
    print(
        "Completed return value: "
        f"{money(completed_return_amount)}"
    )

    check(
        "Completed return value does not exceed gross revenue",
        completed_return_amount <= gross_revenue,
        (
            f"Returns: {money(completed_return_amount)} | "
            f"Revenue: {money(gross_revenue)}"
        )
    )

    net_revenue = gross_revenue - completed_return_amount

    print(f"Net revenue after completed returns: {money(net_revenue)}")

    # ---------------------------------------------------------
    # 4. SALES PAYMENTS AND REFUNDS
    # ---------------------------------------------------------

    print_section("4. CASH COLLECTION RECONCILIATION")

    payment_totals = connection.execute(
        text("""
            SELECT
                COUNT(*) FILTER (
                    WHERE status = 'successful'
                ) AS successful_count,

                COALESCE(SUM(amount_cents) FILTER (
                    WHERE status = 'successful'
                ), 0) AS successful_amount,

                COUNT(*) FILTER (
                    WHERE status = 'pending'
                ) AS pending_count,

                COALESCE(SUM(amount_cents) FILTER (
                    WHERE status = 'pending'
                ), 0) AS pending_amount,

                COUNT(*) FILTER (
                    WHERE status = 'failed'
                ) AS failed_count,

                COALESCE(SUM(amount_cents) FILTER (
                    WHERE status = 'failed'
                ), 0) AS failed_amount,

                COUNT(*) FILTER (
                    WHERE status = 'reversed'
                ) AS reversed_count,

                COALESCE(SUM(amount_cents) FILTER (
                    WHERE status = 'reversed'
                ), 0) AS reversed_amount

            FROM sales_payments
            WHERE dataset_version_id = :version_id
        """),
        params
    ).one()

    refunds = connection.execute(
        text("""
            SELECT
                COUNT(*) FILTER (
                    WHERE status = 'successful'
                ) AS successful_count,

                COALESCE(SUM(amount_cents) FILTER (
                    WHERE status = 'successful'
                ), 0) AS successful_amount,

                COUNT(*) FILTER (
                    WHERE status = 'pending'
                ) AS pending_count,

                COALESCE(SUM(amount_cents) FILTER (
                    WHERE status = 'pending'
                ), 0) AS pending_amount,

                COUNT(*) FILTER (
                    WHERE status = 'failed'
                ) AS failed_count,

                COALESCE(SUM(amount_cents) FILTER (
                    WHERE status = 'failed'
                ), 0) AS failed_amount

            FROM sales_refunds
            WHERE dataset_version_id = :version_id
        """),
        params
    ).one()

    print("SALES PAYMENTS")
    print(
        f"Successful: {payment_totals.successful_count:,} | "
        f"{money(payment_totals.successful_amount)}"
    )
    print(
        f"Pending: {payment_totals.pending_count:,} | "
        f"{money(payment_totals.pending_amount)}"
    )
    print(
        f"Failed: {payment_totals.failed_count:,} | "
        f"{money(payment_totals.failed_amount)}"
    )
    print(
        f"Reversed: {payment_totals.reversed_count:,} | "
        f"{money(payment_totals.reversed_amount)}"
    )

    print("\nSALES REFUNDS")
    print(
        f"Successful: {refunds.successful_count:,} | "
        f"{money(refunds.successful_amount)}"
    )
    print(
        f"Pending: {refunds.pending_count:,} | "
        f"{money(refunds.pending_amount)}"
    )
    print(
        f"Failed: {refunds.failed_count:,} | "
        f"{money(refunds.failed_amount)}"
    )

    net_cash_collections = (
        payment_totals.successful_amount
        - refunds.successful_amount
    )

    print(
        "\nNet cash collections after successful refunds: "
        f"{money(net_cash_collections)}"
    )

    check(
        "Successful sales payments have positive amounts",
        scalar(
            connection,
            """
            SELECT COUNT(*)
            FROM sales_payments
            WHERE dataset_version_id = :version_id
              AND status = 'successful'
              AND amount_cents <= 0
            """,
            params
        ) == 0
    )

    check(
        "Successful refunds have positive amounts",
        scalar(
            connection,
            """
            SELECT COUNT(*)
            FROM sales_refunds
            WHERE dataset_version_id = :version_id
              AND status = 'successful'
              AND amount_cents <= 0
            """,
            params
        ) == 0
    )

    # ---------------------------------------------------------
    # 5. COST OF GOODS SOLD
    # ---------------------------------------------------------

    print_section("5. COST OF GOODS SOLD RECONCILIATION")

    cogs = connection.execute(
        text("""
            SELECT
                COALESCE(SUM(
                    CASE
                        WHEN movement_type = 'sale'
                        THEN ABS(quantity) * unit_cost_cents
                        ELSE 0
                    END
                ), 0) AS sale_cogs,

                COALESCE(SUM(
                    CASE
                        WHEN movement_type = 'customer_return'
                        THEN quantity * unit_cost_cents
                        ELSE 0
                    END
                ), 0) AS returned_cogs

            FROM inventory_movements
            WHERE dataset_version_id = :version_id
        """),
        params
    ).one()

    sale_cogs = cogs.sale_cogs
    returned_cogs = cogs.returned_cogs

    net_cogs = sale_cogs - returned_cogs

    print(f"Cost of goods sold: {money(sale_cogs)}")
    print(f"Returned inventory cost: {money(returned_cogs)}")
    print(f"Net cost of goods sold: {money(net_cogs)}")

    check(
        "Returned inventory cost does not exceed sale COGS",
        returned_cogs <= sale_cogs,
        (
            f"Sale COGS: {money(sale_cogs)} | "
            f"Returned COGS: {money(returned_cogs)}"
        )
    )

    # ---------------------------------------------------------
    # 6. OPERATING EXPENSES
    # ---------------------------------------------------------

    print_section("6. OPERATING EXPENSE RECONCILIATION")

    expense_totals = connection.execute(
        text("""
            SELECT
                COUNT(*) FILTER (
                    WHERE status = 'approved'
                ) AS approved_count,

                COALESCE(SUM(amount_cents) FILTER (
                    WHERE status = 'approved'
                ), 0) AS approved_amount,

                COUNT(*) AS total_count

            FROM expenses
            WHERE dataset_version_id = :version_id
        """),
        params
    ).one()

    expense_payments = connection.execute(
        text("""
            SELECT
                COUNT(*) FILTER (
                    WHERE status = 'successful'
                ) AS successful_count,

                COALESCE(SUM(amount_cents) FILTER (
                    WHERE status = 'successful'
                ), 0) AS successful_amount

            FROM expense_payments
            WHERE dataset_version_id = :version_id
        """),
        params
    ).one()

    approved_expenses = expense_totals.approved_amount
    paid_expenses = expense_payments.successful_amount

    print(f"Total expense records: {expense_totals.total_count:,}")
    print(f"Approved expense records: {expense_totals.approved_count:,}")
    print(f"Approved expenses: {money(approved_expenses)}")
    print(
        f"Successful expense payments: "
        f"{money(paid_expenses)}"
    )

    check(
        "Approved expenses have positive amounts",
        scalar(
            connection,
            """
            SELECT COUNT(*)
            FROM expenses
            WHERE dataset_version_id = :version_id
              AND status = 'approved'
              AND amount_cents <= 0
            """,
            params
        ) == 0
    )

    check(
        "Successful expense payments have positive amounts",
        scalar(
            connection,
            """
            SELECT COUNT(*)
            FROM expense_payments
            WHERE dataset_version_id = :version_id
              AND status = 'successful'
              AND amount_cents <= 0
            """,
            params
        ) == 0
    )

    # ---------------------------------------------------------
    # 7. MARKETING COSTS
    # ---------------------------------------------------------

    print_section("7. MARKETING COST RECONCILIATION")

    marketing = connection.execute(
        text("""
            SELECT
                COUNT(*) AS campaign_count
            FROM marketing_campaigns
            WHERE dataset_version_id = :version_id
        """),
        params
    ).one()

    campaign_costs = connection.execute(
        text("""
            SELECT
                COUNT(*) AS cost_records,
                COALESCE(SUM(amount_cents), 0) AS total_cost
            FROM campaign_costs
            WHERE dataset_version_id = :version_id
        """),
        params
    ).one()

    print(f"Marketing campaigns: {marketing.campaign_count}")
    print(f"Campaign cost records: {campaign_costs.cost_records}")
    print(f"Campaign costs: {money(campaign_costs.total_cost)}")

    print(
        "Note: campaign costs are allocations of existing expenses. "
        "They are not deducted again."
    )

    # ---------------------------------------------------------
    # 8. BUDGET POSITION
    # ---------------------------------------------------------

    print_section("8. BUDGET POSITION")

    budgets = connection.execute(
        text("""
            SELECT
                b.budget_code,
                b.budget_name,
                b.budget_amount_cents,
                b.status,

                COALESCE(SUM(e.amount_cents), 0)
                    AS actual_expense_cents

            FROM budgets b

            LEFT JOIN expenses e
              ON e.dataset_version_id = b.dataset_version_id
             AND e.status = 'approved'
             AND e.expense_date >= b.start_date
             AND e.expense_date < b.end_date + INTERVAL '1 day'
             AND (
                 b.expense_category_id IS NULL
                 OR e.expense_category_id = b.expense_category_id
             )
             AND (
                 b.department_id IS NULL
                 OR e.department_id = b.department_id
             )
             AND (
                 b.store_id IS NULL
                 OR e.store_id = b.store_id
             )

            WHERE b.dataset_version_id = :version_id

            GROUP BY
                b.id,
                b.budget_code,
                b.budget_name,
                b.budget_amount_cents,
                b.status

            ORDER BY b.budget_code
        """),
        params
    ).all()

    print(f"Budget records: {len(budgets)}")

    for budget in budgets:
        variance = (
            budget.budget_amount_cents
            - budget.actual_expense_cents
        )

        if budget.budget_amount_cents:
            utilization = (
                budget.actual_expense_cents
                / budget.budget_amount_cents
            ) * 100
        else:
            utilization = 0

        print(
            f"\n{budget.budget_code} - {budget.budget_name}"
        )
        print(f"Status: {budget.status}")
        print(f"Budget: {money(budget.budget_amount_cents)}")
        print(f"Actual approved expenses: {money(budget.actual_expense_cents)}")
        print(f"Remaining / (over budget): {money(variance)}")
        print(f"Utilization: {utilization:.2f}%")

    print(
        "\nNote: budgets may overlap in category, department, "
        "store or date scope. Their actuals must not be summed "
        "as if each budget represents separate expenses."
    )

    # ---------------------------------------------------------
    # 9. PROFITABILITY RECONCILIATION
    # ---------------------------------------------------------

    print_section("9. PROFITABILITY RECONCILIATION")

    gross_profit = net_revenue - net_cogs
    operating_result = gross_profit - approved_expenses

    if net_revenue:
        gross_margin = gross_profit / net_revenue * 100
    else:
        gross_margin = 0

    if net_revenue:
        operating_margin = operating_result / net_revenue * 100
    else:
        operating_margin = 0

    print(f"Gross sales revenue: {money(gross_revenue)}")
    print(f"Completed sales returns: {money(completed_return_amount)}")
    print(f"Net revenue: {money(net_revenue)}")

    print(f"\nSale COGS: {money(sale_cogs)}")
    print(f"Returned inventory cost: {money(returned_cogs)}")
    print(f"Net COGS: {money(net_cogs)}")

    print(f"\nGross profit: {money(gross_profit)}")
    print(f"Gross margin: {gross_margin:.2f}%")

    print(f"\nApproved operating expenses: {money(approved_expenses)}")
    print(f"Operating result: {money(operating_result)}")
    print(f"Operating margin: {operating_margin:.2f}%")

    check(
        "Net revenue is not negative",
        net_revenue >= 0,
        f"Net revenue: {money(net_revenue)}"
    )

    check(
        "Net COGS is not negative",
        net_cogs >= 0,
        f"Net COGS: {money(net_cogs)}"
    )

    # ---------------------------------------------------------
    # 10. CASH POSITION SUMMARY
    # ---------------------------------------------------------

    print_section("10. OPERATING CASH MOVEMENT SUMMARY")

    operating_cash_proxy = (
        net_cash_collections - paid_expenses
    )

    print(
        "Successful sales collections: "
        f"{money(payment_totals.successful_amount)}"
    )
    print(
        "Less successful customer refunds: "
        f"{money(refunds.successful_amount)}"
    )
    print(
        "Less successful expense payments: "
        f"{money(paid_expenses)}"
    )
    print("-" * 45)
    print(
        "Net cash movement proxy: "
        f"{money(operating_cash_proxy)}"
    )

    print(
        "\nThis is a limited operating cash proxy, not a complete "
        "cash-flow statement. Supplier payments and other cash "
        "movements are not included."
    )

# -------------------------------------------------------------
# FINAL AUDIT RESULT
# -------------------------------------------------------------

print_section("FINAL FINANCIAL RECONCILIATION RESULT")

passed = sum(1 for _, result in audit_results if result)
failed = sum(1 for _, result in audit_results if not result)

print(f"Checks passed: {passed}")
print(f"Checks failed: {failed}")

if failed == 0:
    print("\nRESULT: FINANCIAL RECONCILIATION PASSED")
else:
    print("\nRESULT: FINANCIAL RECONCILIATION REQUIRES INVESTIGATION")

    print("\nFAILED CHECKS:")

    for name, result in audit_results:
        if not result:
            print(f"- {name}")
