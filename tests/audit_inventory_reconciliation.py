
from sqlalchemy import text

from Bizpoint.database.connection import engine
from Bizpoint.data_generation.config import DATASET_NAME


CHECKS = [
    (
        "Purchase receipt movements match accepted receipt items",
        """
        SELECT COUNT(*)
        FROM (
            SELECT
                gri.id,
                gri.quantity_accepted,
                COUNT(im.id) AS movement_count,
                COALESCE(SUM(im.quantity), 0) AS movement_quantity
            FROM goods_receipt_items gri
            JOIN goods_receipts gr
                ON gr.id = gri.goods_receipt_id
                AND gr.dataset_version_id = gri.dataset_version_id
            LEFT JOIN inventory_movements im
                ON im.reference_id = gri.id
                AND im.movement_type = 'purchase_receipt'
                AND im.dataset_version_id = gri.dataset_version_id
            WHERE gri.dataset_version_id = :version_id
              AND gr.status = 'accepted'
              AND gri.quantity_accepted > 0
            GROUP BY gri.id, gri.quantity_accepted
            HAVING COUNT(im.id) <> 1
                OR COALESCE(SUM(im.quantity), 0)
                    <> gri.quantity_accepted
        ) discrepancies
        """,
    ),
    (
        "No unexpected purchase receipt movements",
        """
        SELECT COUNT(*)
        FROM inventory_movements im
        WHERE im.dataset_version_id = :version_id
          AND im.movement_type = 'purchase_receipt'
          AND NOT EXISTS (
              SELECT 1
              FROM goods_receipt_items gri
              JOIN goods_receipts gr
                ON gr.id = gri.goods_receipt_id
                AND gr.dataset_version_id = gri.dataset_version_id
              WHERE gri.id = im.reference_id
                AND gri.dataset_version_id = im.dataset_version_id
                AND gr.status = 'accepted'
                AND gri.quantity_accepted > 0
          )
        """,
    ),
    (
        "Sales movements match completed sales order items",
        """
        SELECT COUNT(*)
        FROM (
            SELECT
                soi.id,
                soi.quantity,
                COUNT(im.id) AS movement_count,
                COALESCE(SUM(im.quantity), 0) AS movement_quantity
            FROM sales_order_items soi
            JOIN sales_orders so
                ON so.id = soi.order_id
                AND so.dataset_version_id = soi.dataset_version_id
            LEFT JOIN inventory_movements im
                ON im.reference_id = soi.id
                AND im.movement_type = 'sale'
                AND im.dataset_version_id = soi.dataset_version_id
            WHERE soi.dataset_version_id = :version_id
              AND so.status = 'completed'
            GROUP BY soi.id, soi.quantity
            HAVING COUNT(im.id) <> 1
                OR COALESCE(SUM(im.quantity), 0) <> -soi.quantity
        ) discrepancies
        """,
    ),
    (
        "No unexpected sale movements",
        """
        SELECT COUNT(*)
        FROM inventory_movements im
        WHERE im.dataset_version_id = :version_id
          AND im.movement_type = 'sale'
          AND NOT EXISTS (
              SELECT 1
              FROM sales_order_items soi
              JOIN sales_orders so
                ON so.id = soi.order_id
                AND so.dataset_version_id = soi.dataset_version_id
              WHERE soi.id = im.reference_id
                AND soi.dataset_version_id = im.dataset_version_id
                AND so.status = 'completed'
          )
        """,
    ),
    (
        "Customer return movements match completed return items",
        """
        SELECT COUNT(*)
        FROM (
            SELECT
                sri.id,
                sri.quantity,
                COUNT(im.id) AS movement_count,
                COALESCE(SUM(im.quantity), 0) AS movement_quantity
            FROM sales_return_items sri
            JOIN sales_returns sr
                ON sr.id = sri.return_id
                AND sr.dataset_version_id = sri.dataset_version_id
            LEFT JOIN inventory_movements im
                ON im.reference_id = sri.id
                AND im.movement_type = 'customer_return'
                AND im.dataset_version_id = sri.dataset_version_id
            WHERE sri.dataset_version_id = :version_id
              AND sr.status = 'completed'
            GROUP BY sri.id, sri.quantity
            HAVING COUNT(im.id) <> 1
                OR COALESCE(SUM(im.quantity), 0) <> sri.quantity
        ) discrepancies
        """,
    ),
    (
        "No unexpected customer return movements",
        """
        SELECT COUNT(*)
        FROM inventory_movements im
        WHERE im.dataset_version_id = :version_id
          AND im.movement_type = 'customer_return'
          AND NOT EXISTS (
              SELECT 1
              FROM sales_return_items sri
              JOIN sales_returns sr
                ON sr.id = sri.return_id
                AND sr.dataset_version_id = sri.dataset_version_id
              WHERE sri.id = im.reference_id
                AND sri.dataset_version_id = im.dataset_version_id
                AND sr.status = 'completed'
          )
        """,
    ),
    (
        "Returned quantities do not exceed sold quantities",
        """
        SELECT COUNT(*)
        FROM (
            SELECT
                sri.order_item_id,
                SUM(sri.quantity) AS returned_quantity,
                soi.quantity AS sold_quantity
            FROM sales_return_items sri
            JOIN sales_returns sr
                ON sr.id = sri.return_id
                AND sr.dataset_version_id = sri.dataset_version_id
            JOIN sales_order_items soi
                ON soi.id = sri.order_item_id
                AND soi.dataset_version_id = sri.dataset_version_id
            WHERE sri.dataset_version_id = :version_id
              AND sr.status = 'completed'
            GROUP BY sri.order_item_id, soi.quantity
            HAVING SUM(sri.quantity) > soi.quantity
        ) excessive_returns
        """,
    ),
    (
        "Inventory movement quantities have valid signs",
        """
        SELECT COUNT(*)
        FROM inventory_movements
        WHERE dataset_version_id = :version_id
          AND (
              (
                  movement_type IN (
                      'opening_stock',
                      'purchase_receipt',
                      'customer_return'
                  )
                  AND quantity <= 0
              )
              OR (
                  movement_type IN ('sale', 'write_off')
                  AND quantity >= 0
              )
          )
        """,
    ),
    (
        "Inventory balances never become negative",
        """
        SELECT COUNT(*)
        FROM (
            SELECT
                product_id,
                store_id,
                SUM(quantity) OVER (
                    PARTITION BY product_id, store_id
                    ORDER BY movement_date, created_at, id
                    ROWS BETWEEN UNBOUNDED PRECEDING
                    AND CURRENT ROW
                ) AS running_quantity
            FROM inventory_movements
            WHERE dataset_version_id = :version_id
        ) balances
        WHERE running_quantity < 0
        """,
    ),
]


def main():
    failures = 0

    with engine.connect() as connection:
        dataset_id = connection.execute(
            text("""
                SELECT id
                FROM datasets
                WHERE name = :dataset_name
            """),
            {"dataset_name": DATASET_NAME},
        ).scalar_one_or_none()

        if dataset_id is None:
            raise RuntimeError(
                f"Dataset '{DATASET_NAME}' was not found."
            )

        version_id = connection.execute(
            text("""
                SELECT id
                FROM dataset_versions
                WHERE dataset_id = :dataset_id
                  AND version_number = 1
            """),
            {"dataset_id": dataset_id},
        ).scalar_one_or_none()

        if version_id is None:
            raise RuntimeError("Dataset version 1 was not found.")

        print("\nINVENTORY RECONCILIATION AUDIT")
        print("=" * 65)
        print(f"Dataset: {DATASET_NAME}")
        print(f"Version ID: {version_id}")
        print("=" * 65)

        for title, query in CHECKS:
            issue_count = connection.execute(
                text(query),
                {"version_id": version_id},
            ).scalar_one()

            status = "PASS" if issue_count == 0 else "FAIL"

            print(
                f"{status}: {title} "
                f"— {issue_count} issue(s)"
            )

            if issue_count:
                failures += 1

        print("\n" + "=" * 65)

        if failures == 0:
            print("RESULT: ALL CHECKS PASSED")
        else:
            print(f"RESULT: {failures} CHECK(S) FAILED")

        print("=" * 65)


if __name__ == "__main__":
    main()
