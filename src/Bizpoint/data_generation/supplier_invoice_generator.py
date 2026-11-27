
from datetime import timedelta

from sqlalchemy import select, func

from Bizpoint.database.connection import SessionLocal
from Bizpoint.database.models import (
    Dataset,
    DatasetVersion,
    PurchaseOrder,
    PurchaseOrderItem,
    GoodsReceipt,
    GoodsReceiptItem,
    SupplierInvoice,
)

from Bizpoint.data_generation.config import DATASET_NAME
from Bizpoint.data_generation.utils import create_generators


def generate_supplier_invoices():

    random_generator, numpy_generator, fake = create_generators()

    with SessionLocal() as session:
        with session.begin():

            dataset = session.scalar(
                select(Dataset).where(
                    Dataset.name == DATASET_NAME
                )
            )

            if dataset is None:
                raise ValueError("Dataset does not exist.")

            version = session.scalar(
                select(DatasetVersion).where(
                    DatasetVersion.dataset_id == dataset.id,
                    DatasetVersion.version_number == 1,
                )
            )

            if version is None:
                raise ValueError("Dataset version does not exist.")

            version_id = version.id

            purchase_orders = session.scalars(
                select(PurchaseOrder).where(
                PurchaseOrder.dataset_version_id == version_id
                )
            ).all()

            existing_po_ids = set(
                session.scalars(
                    select(SupplierInvoice.purchase_order_id).where(
                        SupplierInvoice.dataset_version_id == version_id,
                        SupplierInvoice.purchase_order_id.is_not(None),
                    )
                ).all()
            )

            existing_invoice_numbers = set(
                session.scalars(
                    select(SupplierInvoice.invoice_number).where(
                        SupplierInvoice.dataset_version_id == version_id
                    )
                ).all()
            )

            new_invoices = 0
            skipped_orders = 0
            invoice_number = 1

            for purchase_order in purchase_orders:

                if purchase_order.id in existing_po_ids:
                    skipped_orders += 1
                    continue

                po_items = session.scalars(
                    select(PurchaseOrderItem).where(
                        PurchaseOrderItem.dataset_version_id == version_id,
                        PurchaseOrderItem.purchase_order_id == purchase_order.id,
                    )
                ).all()

                total_invoice_amount = 0

                for po_item in po_items:

                    receipt_items = session.scalars(
                        select(GoodsReceiptItem).where(
                            GoodsReceiptItem.dataset_version_id == version_id,
                            GoodsReceiptItem.purchase_order_item_id == po_item.id,
                        )
                    ).all()

                    for receipt_item in receipt_items:

                        total_invoice_amount += (
                            receipt_item.quantity_accepted
                            * receipt_item.unit_cost_cents
                        )

                if total_invoice_amount <= 0:
                    skipped_orders += 1
                    continue

                while (
                    f"INV{invoice_number:06d}"
                    in existing_invoice_numbers
                ):
                    invoice_number += 1

                invoice_code = f"INV{invoice_number:06d}"
                invoice_number += 1

                invoice_date = (
                    purchase_order.order_date
                    + timedelta(
                        days=random_generator.randint(1, 10)
                    )
                )

                due_date = invoice_date + timedelta(
                    days=random_generator.choice([15, 30, 45])
                )

                status = random_generator.choices(
                    [
                        "approved",
                        "submitted",
                        "draft",
                        "disputed",
                    ],
                    weights=[75, 12, 8, 5],
                    k=1,
                )[0]

                invoice = SupplierInvoice(
                    dataset_version_id=version_id,
                    invoice_number=invoice_code,
                    supplier_id=purchase_order.supplier_id,
                    purchase_order_id=purchase_order.id,
                    invoice_date=invoice_date,
                    due_date=due_date,
                    invoice_amount_cents=total_invoice_amount,
                    status=status,
                )

                session.add(invoice)

                existing_po_ids.add(purchase_order.id)
                existing_invoice_numbers.add(invoice_code)

                new_invoices += 1

            session.flush()

            total_invoices = session.scalar(
                select(func.count()).select_from(
                    SupplierInvoice
                ).where(
                    SupplierInvoice.dataset_version_id == version_id
                )
            )

            total_amount = session.scalar(
                select(func.coalesce(
                    func.sum(SupplierInvoice.invoice_amount_cents),
                    0,
                )).where(
                    SupplierInvoice.dataset_version_id == version_id
                )
            )

    return {
        "dataset_version_id": version_id,
        "new_invoices_created": new_invoices,
        "purchase_orders_skipped": skipped_orders,
        "total_supplier_invoices": total_invoices,
        "total_invoiced_amount_cents": total_amount,
    }


if __name__ == "__main__":

    result = generate_supplier_invoices()

    print("\nSUPPLIER INVOICE GENERATION COMPLETED")

    for key, value in result.items():
        print(f"{key}: {value}")
