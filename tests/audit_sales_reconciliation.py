
from sqlalchemy import select
from Bizpoint.database.base import Base
from Bizpoint.database.connection import SessionLocal
import Bizpoint.database.models


DATASET_VERSION_ID = "b580a1d713b1425685bbc624ef8473b6"

tables = Base.metadata.tables

sales_orders = tables["sales_orders"]
sales_order_items = tables["sales_order_items"]
sales_order_item_taxes = tables["sales_order_item_taxes"]


def audit_sales_reconciliation():
    session = SessionLocal()

    try:
        # 1. Retrieve all sales orders for this dataset version.
        orders = session.execute(
            select(
                sales_orders.c.id,
                sales_orders.c.order_number,
                sales_orders.c.status,
                sales_orders.c.total_amount_cents,
            ).where(
                sales_orders.c.dataset_version_id == DATASET_VERSION_ID
            )
        ).mappings().all()

        # 2. Retrieve all sales order items.
        items = session.execute(
            select(
                sales_order_items.c.order_id,
                sales_order_items.c.quantity,
                sales_order_items.c.original_unit_price_cents,
                sales_order_items.c.discount_amount_cents,
            ).where(
                sales_order_items.c.dataset_version_id
                == DATASET_VERSION_ID
            )
        ).mappings().all()

        # 3. Calculate item totals for each order.
        item_totals = {}

        for item in items:
            line_total = (
                item["quantity"] * item["original_unit_price_cents"]
                - item["discount_amount_cents"]
            )

            item_totals[item["order_id"]] = (
                item_totals.get(item["order_id"], 0) + line_total
            )

        # 4. Compare order totals against item totals.
        mismatches = []

        for order in orders:
            calculated_total = item_totals.get(order["id"], 0)
            recorded_total = order["total_amount_cents"]

            if calculated_total != recorded_total:
                mismatches.append({
                    "order_number": order["order_number"],
                    "status": order["status"],
                    "recorded": recorded_total,
                    "calculated": calculated_total,
                    "difference": recorded_total - calculated_total,
                })

        # 5. Calculate completed sales.
        completed_orders = [
            order for order in orders
            if order["status"] == "completed"
        ]

        completed_sales = sum(
            order["total_amount_cents"]
            for order in completed_orders
        )

        # 6. Retrieve VAT totals.
        tax_records = session.execute(
            select(
                sales_order_item_taxes.c.taxable_amount_cents,
                sales_order_item_taxes.c.tax_amount_cents,
            ).where(
                sales_order_item_taxes.c.dataset_version_id
                == DATASET_VERSION_ID
            )
        ).mappings().all()

        total_taxable = sum(
            tax["taxable_amount_cents"] for tax in tax_records
        )

        total_vat = sum(
            tax["tax_amount_cents"] for tax in tax_records
        )

        completed_item_sales = sum(
            item_totals.get(order["id"], 0)
            for order in completed_orders
        )

        # 7. Report results.
        print("\nSALES FINANCIAL RECONCILIATION")
        print("=" * 40)

        print(f"Sales orders: {len(orders)}")
        print(f"Sales order items: {len(items)}")
        print(f"Completed orders: {len(completed_orders)}")

        print("\nORDER TOTAL RECONCILIATION")
        print(f"Orders with mismatched totals: {len(mismatches)}")

        print("\nCOMPLETED SALES")
        print(f"Recorded order totals: ${completed_sales / 100:,.2f}")
        print(f"Calculated item totals: ${completed_item_sales / 100:,.2f}")

        print("\nVAT RECONCILIATION")
        print(f"VAT records: {len(tax_records)}")
        print(f"Taxable amount: ${total_taxable / 100:,.2f}")
        print(f"Calculated VAT: ${total_vat / 100:,.2f}")

        print("\nTAXABLE SALES COMPARISON")
        print(
            f"Completed item sales: "
            f"${completed_item_sales / 100:,.2f}"
        )
        print(f"Recorded taxable sales: ${total_taxable / 100:,.2f}")

        taxable_difference = completed_item_sales - total_taxable
        print(
            f"Difference: ${taxable_difference / 100:,.2f}"
        )

        print("\nMISMATCH DETAILS")

        for mismatch in mismatches[:10]:
            print(mismatch)

        if not mismatches and taxable_difference == 0:
            print("\nRESULT: PASSED")
        else:
            print("\nRESULT: REVIEW REQUIRED")

    finally:
        session.close()


if __name__ == "__main__":
    audit_sales_reconciliation()
