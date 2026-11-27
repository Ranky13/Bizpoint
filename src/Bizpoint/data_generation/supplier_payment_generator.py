
from datetime import timedelta

from sqlalchemy import select, func

from Bizpoint.database.connection import SessionLocal
from Bizpoint.database.models import (
    Dataset,
    DatasetVersion,
    SupplierInvoice,
    SupplierPayment,
)

from Bizpoint.data_generation.config import DATASET_NAME
from Bizpoint.data_generation.utils import create_generators


def generate_supplier_payments():

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

            invoices = session.scalars(
                select(SupplierInvoice).where(
                    SupplierInvoice.dataset_version_id == version_id,
                    SupplierInvoice.status == "approved",
                ).order_by(SupplierInvoice.invoice_number)
            ).all()

            existing_invoice_ids = set(
                session.scalars(
                    select(SupplierPayment.supplier_invoice_id).where(
                        SupplierPayment.dataset_version_id == version_id
                    )
                ).all()
            )

            new_payments = 0
            skipped_invoices = 0

            for invoice in invoices:

                if invoice.id in existing_invoice_ids:
                    skipped_invoices += 1
                    continue

                payment_date = invoice.invoice_date + timedelta(
                    days=random_generator.randint(1, 45)
                )

                payment_status = random_generator.choices(
                    [
                        "successful",
                        "pending",
                        "failed",
                    ],
                    weights=[75, 15, 10],
                    k=1,
                )[0]

                # Generate a partial or full payment.
                if payment_status == "successful":
                    payment_percentage = random_generator.choice(
                        [0.25, 0.50, 0.75, 1.00]
                    )

                else:
                    payment_percentage = random_generator.choice(
                        [0.25, 0.50, 0.75]
                    )

                payment_amount = int(
                    invoice.invoice_amount_cents
                    * payment_percentage
                )

                payment_amount = max(1, payment_amount)

                payment = SupplierPayment(
                    dataset_version_id=version_id,
                    supplier_invoice_id=invoice.id,
                    payment_reference=(
                        f"SPAY-{invoice.invoice_number}"
                    ),
                    payment_date=payment_date,
                    amount_cents=payment_amount,
                    status=payment_status,
                )

                session.add(payment)
                existing_invoice_ids.add(invoice.id)
                new_payments += 1

            session.flush()

            total_payments = session.scalar(
                select(func.count()).select_from(
                    SupplierPayment
                ).where(
                    SupplierPayment.dataset_version_id == version_id
                )
            )

            payment_status_counts = {}

            for status in [
                "successful",
                "pending",
                "failed",
                "reversed",
            ]:

                payment_status_counts[status] = session.scalar(
                    select(func.count()).select_from(
                        SupplierPayment
                    ).where(
                        SupplierPayment.dataset_version_id == version_id,
                        SupplierPayment.status == status,
                    )
                )

            successful_amount = session.scalar(
                select(
                    func.coalesce(
                        func.sum(SupplierPayment.amount_cents),
                        0,
                    )
                ).where(
                    SupplierPayment.dataset_version_id == version_id,
                    SupplierPayment.status == "successful",
                )
            )

    return {
        "dataset_version_id": version_id,
        "new_payments_created": new_payments,
        "existing_invoices_skipped": skipped_invoices,
        "total_supplier_payments": total_payments,
        "successful_payments": payment_status_counts["successful"],
        "pending_payments": payment_status_counts["pending"],
        "failed_payments": payment_status_counts["failed"],
        "reversed_payments": payment_status_counts["reversed"],
        "successful_payment_amount_cents": successful_amount,
    }


if __name__ == "__main__":

    result = generate_supplier_payments()

    print("\nSUPPLIER PAYMENT GENERATION COMPLETED")

    for key, value in result.items():
        print(f"{key}: {value}")
