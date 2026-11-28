
from sqlalchemy import text

from Bizpoint.database.connection import engine
from Bizpoint.data_generation.config import DATASET_NAME


def get_dataset_version_id(connection):
    query = text("""
        SELECT dv.id
        FROM dataset_versions dv
        JOIN datasets d ON d.id = dv.dataset_id
        WHERE d.name = :dataset_name
        ORDER BY dv.version_number DESC
        LIMIT 1
    """)

    result = connection.execute(
        query,
        {"dataset_name": DATASET_NAME}
    ).scalar_one_or_none()

    if result is None:
        raise RuntimeError(
            f"Dataset version not found for: {DATASET_NAME}"
        )

    return result


def run_check(connection, title, query, params):
    result = connection.execute(text(query), params).scalar_one()

    print(f"{title}: {result}")

    return result


def main():
    print("=" * 65)
    print("BIZPOINT PROCUREMENT AUDIT")
    print("=" * 65)

    with engine.connect() as connection:
        version_id = get_dataset_version_id(connection)
        params = {"version_id": version_id}

        print(f"Dataset: {DATASET_NAME}")
        print(f"Dataset version: {version_id}")
        print()

        # --------------------------------------------------
        # RECORD COUNTS
        # --------------------------------------------------

        print("PROCUREMENT RECORD COUNTS")
        print("-" * 65)

        counts = {
            "Purchase orders": """
                SELECT COUNT(*) FROM purchase_orders
                WHERE dataset_version_id = :version_id
            """,
            "Purchase order items": """
                SELECT COUNT(*) FROM purchase_order_items
                WHERE dataset_version_id = :version_id
            """,
            "Goods receipts": """
                SELECT COUNT(*) FROM goods_receipts
                WHERE dataset_version_id = :version_id
            """,
            "Goods receipt items": """
                SELECT COUNT(*) FROM goods_receipt_items
                WHERE dataset_version_id = :version_id
            """,
            "Supplier invoices": """
                SELECT COUNT(*) FROM supplier_invoices
                WHERE dataset_version_id = :version_id
            """,
            "Supplier payments": """
                SELECT COUNT(*) FROM supplier_payments
                WHERE dataset_version_id = :version_id
            """,
        }

        for label, query in counts.items():
            count = run_check(
                connection,
                label,
                query,
                params
            )

        print()

        # --------------------------------------------------
        # CHECK 1: RECEIVED QUANTITY MUST NOT EXCEED
        # PURCHASE ORDER QUANTITY
        # --------------------------------------------------

        print("PROCUREMENT INTEGRITY CHECKS")
        print("-" * 65)

        check_1 = run_check(
            connection,
            "1. Purchase order quantity exceeded",
            """
            SELECT COUNT(*)
            FROM (
                SELECT
                    poi.id,
                    poi.quantity,
                    COALESCE(SUM(gri.quantity_received), 0)
                        AS received_quantity
                FROM purchase_order_items poi
                LEFT JOIN goods_receipt_items gri
                    ON gri.purchase_order_item_id = poi.id
                    AND gri.dataset_version_id = :version_id
                WHERE poi.dataset_version_id = :version_id
                GROUP BY poi.id, poi.quantity
                HAVING COALESCE(SUM(gri.quantity_received), 0)
                    > poi.quantity
            ) violations
            """,
            params
        )

        # --------------------------------------------------
        # CHECK 2: RECEIPT ITEM MUST BELONG TO THE SAME
        # PURCHASE ORDER AS ITS RECEIPT HEADER
        # --------------------------------------------------

        check_2 = run_check(
            connection,
            "2. Goods receipt / purchase order mismatches",
            """
            SELECT COUNT(*)
            FROM goods_receipt_items gri
            JOIN goods_receipts gr
                ON gr.id = gri.goods_receipt_id
            JOIN purchase_order_items poi
                ON poi.id = gri.purchase_order_item_id
            WHERE gri.dataset_version_id = :version_id
              AND gr.dataset_version_id = :version_id
              AND poi.dataset_version_id = :version_id
              AND gr.purchase_order_id <> poi.purchase_order_id
            """,
            params
        )

        # --------------------------------------------------
        # CHECK 3: RECEIVED QUANTITY MUST EQUAL ACCEPTED
        # PLUS REJECTED QUANTITY
        # --------------------------------------------------

        check_3 = run_check(
            connection,
            "3. Goods receipt quantity breakdown errors",
            """
            SELECT COUNT(*)
            FROM goods_receipt_items
            WHERE dataset_version_id = :version_id
              AND quantity_received <>
                  quantity_accepted + quantity_rejected
            """,
            params
        )

        # --------------------------------------------------
        # CHECK 4: PURCHASE ORDER RECEIPT STATUS
        #
        # Only checks statuses whose meaning is explicit:
        # partially_received and received.
        # It does not assume that every other PO status
        # must have zero receipts.
        # --------------------------------------------------

        check_4 = run_check(
            connection,
            "4. Purchase order receipt status inconsistencies",
            """
            SELECT COUNT(*)
            FROM (
                SELECT
                    po.id,
                    po.status,
                    COALESCE(SUM(poi.quantity), 0)
                        AS ordered_quantity,
                    COALESCE(SUM(received.received_quantity), 0)
                        AS received_quantity
                FROM purchase_orders po
                JOIN purchase_order_items poi
                    ON poi.purchase_order_id = po.id
                    AND poi.dataset_version_id = :version_id
                LEFT JOIN (
                    SELECT
                        gri.purchase_order_item_id,
                        SUM(gri.quantity_received)
                            AS received_quantity
                    FROM goods_receipt_items gri
                    JOIN goods_receipts gr
                        ON gr.id = gri.goods_receipt_id
                    WHERE gri.dataset_version_id = :version_id
                      AND gr.dataset_version_id = :version_id
                    GROUP BY gri.purchase_order_item_id
                ) received
                    ON received.purchase_order_item_id = poi.id
                WHERE po.dataset_version_id = :version_id
                GROUP BY po.id, po.status
            ) po_totals
            WHERE
                (
                    status = 'received'
                    AND received_quantity < ordered_quantity
                )
                OR
                (
                    status = 'partially_received'
                    AND (
                        received_quantity <= 0
                        OR received_quantity >= ordered_quantity
                    )
                )
            """,
            params
        )

        # --------------------------------------------------
        # CHECK 5: SUPPLIER INVOICE MUST MATCH THE SUPPLIER
        # ON ITS LINKED PURCHASE ORDER
        #
        # Invoice amounts are deliberately NOT compared
        # with receipt values: partial invoices and other
        # invoice charges may be legitimate.
        # --------------------------------------------------

        check_5 = run_check(
            connection,
            "5. Supplier invoice / purchase order mismatches",
            """
            SELECT COUNT(*)
            FROM supplier_invoices si
            JOIN purchase_orders po
                ON po.id = si.purchase_order_id
            WHERE si.dataset_version_id = :version_id
              AND po.dataset_version_id = :version_id
              AND si.supplier_id <> po.supplier_id
            """,
            params
        )

        # --------------------------------------------------
        # CHECK 6: SUCCESSFUL PAYMENTS MUST NOT EXCEED
        # APPROVED INVOICE AMOUNTS
        #
        # Partial payments are allowed.
        # Only successful payments reduce the payable.
        # --------------------------------------------------

        check_6 = run_check(
            connection,
            "6. Approved supplier invoices overpaid",
            """
            SELECT COUNT(*)
            FROM (
                SELECT
                    si.id,
                    si.invoice_amount_cents,
                    COALESCE(
                        SUM(
                            CASE
                                WHEN sp.status = 'successful'
                                THEN sp.amount_cents
                                ELSE 0
                            END
                        ),
                        0
                    ) AS successful_payments
                FROM supplier_invoices si
                LEFT JOIN supplier_payments sp
                    ON sp.supplier_invoice_id = si.id
                    AND sp.dataset_version_id = :version_id
                WHERE si.dataset_version_id = :version_id
                  AND si.status = 'approved'
                GROUP BY si.id, si.invoice_amount_cents
                HAVING COALESCE(
                    SUM(
                        CASE
                            WHEN sp.status = 'successful'
                            THEN sp.amount_cents
                            ELSE 0
                        END
                    ),
                    0
                ) > si.invoice_amount_cents
            ) overpaid
            """,
            params
        )

        # --------------------------------------------------
        # CHECK 7: INVALID SUPPLIER PAYMENT STATUS
        # --------------------------------------------------

        check_7 = run_check(
            connection,
            "7. Invalid supplier payment statuses",
            """
            SELECT COUNT(*)
            FROM supplier_payments
            WHERE dataset_version_id = :version_id
              AND status NOT IN (
                  'pending',
                  'successful',
                  'failed',
                  'reversed'
              )
            """,
            params
        )

        # --------------------------------------------------
        # CHECK 8: NON-POSITIVE INVOICE OR PAYMENT AMOUNTS
        # --------------------------------------------------

        check_8a = run_check(
            connection,
            "8a. Invalid supplier invoice amounts",
            """
            SELECT COUNT(*)
            FROM supplier_invoices
            WHERE dataset_version_id = :version_id
              AND invoice_amount_cents <= 0
            """,
            params
        )

        check_8b = run_check(
            connection,
            "8b. Invalid supplier payment amounts",
            """
            SELECT COUNT(*)
            FROM supplier_payments
            WHERE dataset_version_id = :version_id
              AND amount_cents <= 0
            """,
            params
        )

        # --------------------------------------------------
        # SUMMARY
        # --------------------------------------------------

        print()
        print("=" * 65)
        print("PROCUREMENT AUDIT SUMMARY")
        print("=" * 65)

        checks = {
            "Purchase order quantity exceeded": check_1,
            "Goods receipt / PO mismatches": check_2,
            "Goods receipt quantity breakdown errors": check_3,
            "PO receipt status inconsistencies": check_4,
            "Invoice / PO supplier mismatches": check_5,
            "Approved invoices overpaid": check_6,
            "Invalid supplier payment statuses": check_7,
            "Invalid supplier invoice amounts": check_8a,
            "Invalid supplier payment amounts": check_8b,
        }

        total_issues = sum(checks.values())

        for label, issue_count in checks.items():
            result = "PASS" if issue_count == 0 else "ISSUES FOUND"
            print(f"{label}: {result} ({issue_count})")

        print("-" * 65)

        if total_issues == 0:
            print("RESULT: PROCUREMENT AUDIT PASSED")
        else:
            print(
                f"RESULT: {total_issues} PROCUREMENT "
                "ISSUE(S) REQUIRE REVIEW"
            )

        print("=" * 65)


if __name__ == "__main__":
    main()
