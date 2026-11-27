
from datetime import timedelta

from sqlalchemy import select, func

from Bizpoint.database.connection import SessionLocal
from Bizpoint.database.models import (
    Dataset,
    DatasetVersion,
    SalesOrder,
    SalesPayment,
    PaymentMethod,
)

from Bizpoint.data_generation.config import DATASET_NAME
from Bizpoint.data_generation.utils import create_generators


def generate_sales_payments():

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

            orders = session.scalars(
                select(SalesOrder).where(
                    SalesOrder.dataset_version_id == version_id
                ).order_by(SalesOrder.order_number)
            ).all()

            payment_methods = session.scalars(
                select(PaymentMethod).where(
                    PaymentMethod.dataset_version_id == version_id,
                    PaymentMethod.is_active.is_(True),
                )
            ).all()

            if not payment_methods:
                raise ValueError("No active payment methods found.")

            existing_order_ids = set(
                session.scalars(
                    select(SalesPayment.order_id).where(
                        SalesPayment.dataset_version_id == version_id
                    )
                ).all()
            )

            new_payments = 0
            skipped_orders = 0

            for order in orders:

                if order.id in existing_order_ids:
                    skipped_orders += 1
                    continue

                if order.total_amount_cents <= 0:
                    skipped_orders += 1
                    continue

                # Determine payment status from order status.
                if order.status == "completed":
                    payment_status = "successful"

                elif order.status == "processing":
                    payment_status = random_generator.choices(
                        ["successful", "pending"],
                        weights=[80, 20],
                        k=1,
                    )[0]

                elif order.status == "pending":
                    payment_status = random_generator.choices(
                        ["pending", "successful", "failed"],
                        weights=[65, 25, 10],
                        k=1,
                    )[0]

                else:
                    payment_status = random_generator.choices(
                        ["failed", "reversed"],
                        weights=[30, 70],
                        k=1,
                    )[0]

                payment_date = (
                    order.order_date
                    + timedelta(
                        minutes=random_generator.randint(1, 180)
                    )
                )

                payment = SalesPayment(
                    dataset_version_id=version_id,
                    order_id=order.id,
                    payment_method_id=random_generator.choice(
                        payment_methods
                    ).id,
                    payment_reference=f"PAY-{order.order_number}",
                    amount_cents=order.total_amount_cents,
                    status=payment_status,
                    payment_date=payment_date,
                )

                session.add(payment)
                new_payments += 1

            session.flush()

            total_payments = session.scalar(
                select(func.count()).select_from(
                    SalesPayment
                ).where(
                    SalesPayment.dataset_version_id == version_id
                )
            )

            status_counts = {}

            for status in [
                "successful",
                "pending",
                "failed",
                "reversed",
            ]:
                status_counts[status] = session.scalar(
                    select(func.count()).select_from(
                        SalesPayment
                    ).where(
                        SalesPayment.dataset_version_id == version_id,
                        SalesPayment.status == status,
                    )
                )

    return {
        "dataset_version_id": version_id,
        "new_payments_created": new_payments,
        "existing_orders_skipped": skipped_orders,
        "total_sales_payments": total_payments,
        **{
            f"{status}_payments": count
            for status, count in status_counts.items()
        },
    }


if __name__ == "__main__":

    result = generate_sales_payments()

    print("\nSALES PAYMENT GENERATION COMPLETED")

    for key, value in result.items():
        print(f"{key}: {value}")
