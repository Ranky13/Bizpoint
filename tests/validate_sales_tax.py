
from sqlalchemy import select, func
from Bizpoint.database.base import Base
from Bizpoint.database.connection import SessionLocal
import Bizpoint.database.models


VAT_RATE = 750
EXPECTED_TAX_NAME = "Nigeria VAT"

tables = Base.metadata.tables

sales_orders = tables["sales_orders"]
sales_order_items = tables["sales_order_items"]
sales_order_item_taxes = tables["sales_order_item_taxes"]
dataset_versions = tables["dataset_versions"]

DATASET_VERSION_ID = "b580a1d713b1425685bbc624ef8473b6"


def validate_sales_tax():
    session = SessionLocal()

    try:
        # Retrieve completed sales items.
        completed_items = (
            select(
                sales_order_items.c.id,
                sales_order_items.c.quantity,
                sales_order_items.c.original_unit_price_cents,
                sales_order_items.c.discount_amount_cents,
            )
            .select_from(
                sales_order_items.join(
                    sales_orders,
                    sales_order_items.c.order_id == sales_orders.c.id,
                )
            )
            .where(
                sales_order_items.c.dataset_version_id == DATASET_VERSION_ID,
                sales_orders.c.status == "completed",
            )
        )

        items = session.execute(completed_items).mappings().all()

        # Retrieve generated VAT records.
        tax_query = select(sales_order_item_taxes).where(
            sales_order_item_taxes.c.dataset_version_id
            == DATASET_VERSION_ID
        )

        taxes = session.execute(tax_query).mappings().all()

        item_map = {item["id"]: item for item in items}
        tax_map = {}

        duplicate_records = 0
        invalid_rates = 0
        invalid_names = 0
        invalid_bases = 0
        invalid_amounts = 0
        invalid_links = 0

        for tax in taxes:
            item_id = tax["order_item_id"]

            if item_id in tax_map:
                duplicate_records += 1

            tax_map[item_id] = tax

            if tax["tax_rate_basis_points"] != VAT_RATE:
                invalid_rates += 1

            if tax["tax_name"] != EXPECTED_TAX_NAME:
                invalid_names += 1

            if item_id not in item_map:
                invalid_links += 1
                continue

            item = item_map[item_id]

            expected_base = (
                item["quantity"] * item["original_unit_price_cents"]
                - item["discount_amount_cents"]
            )

            expected_tax = (
                expected_base * VAT_RATE + 5000
            ) // 10000

            if tax["taxable_amount_cents"] != expected_base:
                invalid_bases += 1

            if tax["tax_amount_cents"] != expected_tax:
                invalid_amounts += 1

        missing_records = len(set(item_map) - set(tax_map))

        total_taxable = sum(
            tax["taxable_amount_cents"] for tax in taxes
        )

        total_vat = sum(
            tax["tax_amount_cents"] for tax in taxes
        )

        print("\nSALES TAX VALIDATION")
        print("--------------------")
        print(f"Completed sales items: {len(items)}")
        print(f"VAT records: {len(taxes)}")
        print(f"Missing records: {missing_records}")
        print(f"Duplicate records: {duplicate_records}")
        print(f"Invalid VAT rates: {invalid_rates}")
        print(f"Invalid VAT names: {invalid_names}")
        print(f"Invalid taxable bases: {invalid_bases}")
        print(f"Invalid VAT amounts: {invalid_amounts}")
        print(f"Invalid item links: {invalid_links}")
        print(f"Total taxable amount: ${total_taxable / 100:,.2f}")
        print(f"Total VAT: ${total_vat / 100:,.2f}")

        passed = all(
            value == 0
            for value in [
                missing_records,
                duplicate_records,
                invalid_rates,
                invalid_names,
                invalid_bases,
                invalid_amounts,
                invalid_links,
            ]
        ) and len(items) == len(taxes)

        print("\nRESULT:", "PASSED" if passed else "FAILED")

    finally:
        session.close()


if __name__ == "__main__":
    validate_sales_tax()
