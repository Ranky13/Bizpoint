
import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, func, insert, select

from Bizpoint.database.base import Base
from Bizpoint.database.connection import SessionLocal
from Bizpoint.data_generation.config import DATASET_NAME

# Register all database models with SQLAlchemy metadata.
import Bizpoint.database.models  # noqa: F401


VAT_NAME = "Nigeria VAT"
VAT_RATE_BASIS_POINTS = 750

tables = Base.metadata.tables

datasets = tables["datasets"]
versions = tables["dataset_versions"]
orders = tables["sales_orders"]
order_items = tables["sales_order_items"]
taxes = tables["sales_order_item_taxes"]


def generate_sales_taxes():
    with SessionLocal() as session:

        # 1. Retrieve the existing dataset.
        dataset_id = session.scalar(
            select(datasets.c.id).where(
                datasets.c.name == DATASET_NAME
            )
        )

        if not dataset_id:
            raise ValueError("Dataset not found.")

        # 2. Retrieve version 1.
        version_id = session.scalar(
            select(versions.c.id).where(
                versions.c.dataset_id == dataset_id,
                versions.c.version_number == 1,
            )
        )

        if not version_id:
            raise ValueError("Dataset version 1 not found.")

        # 3. Prevent duplicate generation.
        existing_count = session.scalar(
            select(func.count())
            .select_from(taxes)
            .where(taxes.c.dataset_version_id == version_id)
        )

        if existing_count:
            print("SALES TAX GENERATION SKIPPED")
            print(f"Existing VAT records: {existing_count}")
            print("No duplicate records created.")
            return

        # 4. Retrieve completed sales order items.
        statement = (
            select(
                order_items.c.id,
                order_items.c.quantity,
                order_items.c.original_unit_price_cents,
                order_items.c.discount_amount_cents,
            )
            .select_from(
                order_items.join(
                    orders,
                    and_(
                        order_items.c.order_id == orders.c.id,
                        order_items.c.dataset_version_id
                        == orders.c.dataset_version_id,
                    ),
                )
            )
            .where(
                order_items.c.dataset_version_id == version_id,
                orders.c.status == "completed",
            )
        )

        completed_items = session.execute(statement).all()

        if not completed_items:
            print("No completed sales order items found.")
            return

        # 5. Calculate VAT for each completed item.
        now = datetime.now(timezone.utc)
        tax_records = []

        for item in completed_items:

            gross_amount = (
                item.quantity
                * item.original_unit_price_cents
            )

            taxable_amount = (
                gross_amount
                - item.discount_amount_cents
            )

            if taxable_amount < 0:
                raise ValueError(
                    f"Negative taxable amount for item {item.id}"
                )

            # Integer arithmetic with half-up rounding.
            tax_amount = (
                taxable_amount * VAT_RATE_BASIS_POINTS + 5000
            ) // 10000

            tax_records.append({
                "id": uuid.uuid4().hex,
                "dataset_version_id": version_id,
                "order_item_id": item.id,
                "tax_name": VAT_NAME,
                "tax_rate_basis_points": VAT_RATE_BASIS_POINTS,
                "taxable_amount_cents": taxable_amount,
                "tax_amount_cents": tax_amount,
                "created_at": now,
                "updated_at": now,
            })

        # 6. Insert all VAT records in one transaction.
        session.execute(
            insert(taxes),
            tax_records,
        )

        session.commit()

        # 7. Display generation results.
        total_taxable = sum(
            record["taxable_amount_cents"]
            for record in tax_records
        )

        total_vat = sum(
            record["tax_amount_cents"]
            for record in tax_records
        )

        print("\nSALES TAX GENERATION COMPLETED")
        print(f"Dataset version: {version_id}")
        print(f"VAT name: {VAT_NAME}")
        print("VAT rate: 7.5%")
        print(f"Completed sales items: {len(completed_items)}")
        print(f"VAT records created: {len(tax_records)}")
        print(
            f"Total taxable amount: ${total_taxable / 100:,.2f}"
        )
        print(f"Total VAT: ${total_vat / 100:,.2f}")


if __name__ == "__main__":
    generate_sales_taxes()
