
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func

from Bizpoint.database.connection import SessionLocal
from Bizpoint.database.models import (
    Dataset,
    DatasetVersion,
    SalesOrder,
    SalesOrderItem,
    SalesReturn,
    SalesReturnItem,
    SalesRefund,
    PaymentMethod,
)

from Bizpoint.data_generation.config import (
    DATASET_NAME,
    END_DATE,
)

from Bizpoint.data_generation.utils import create_generators


def generate_sales_returns():
    """Generate customer returns and associated refund records."""

    random_generator, numpy_generator, fake = create_generators()

    return_rate = 0.10

    return_reasons = [
        "Damaged product",
        "Wrong product delivered",
        "Product not as described",
        "Defective product",
        "Customer changed their mind",
        "Incorrect product size or specification",
        "Product quality issue",
    ]

    with SessionLocal() as session:
        with session.begin():

            # Retrieve dataset and version.
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
                raise ValueError("Dataset version 1 does not exist.")

            version_id = version.id

            # Retrieve completed sales orders.
            completed_orders = session.scalars(
                select(SalesOrder).where(
                    SalesOrder.dataset_version_id == version_id,
                    SalesOrder.status == "completed",
                ).order_by(SalesOrder.order_number)
            ).all()

            if not completed_orders:
                raise ValueError("No completed sales orders found.")

            # Retrieve existing returns to prevent duplicate order returns.
            existing_order_ids = set(
                session.scalars(
                    select(SalesReturn.order_id).where(
                        SalesReturn.dataset_version_id == version_id
                    )
                ).all()
            )

            # Determine the target number of returns.
            target_returns = round(
                len(completed_orders) * return_rate
            )

            remaining_returns = max(
                0,
                target_returns - len(existing_order_ids),
            )

            # Select orders that have not already been returned.
            eligible_orders = [
                order
                for order in completed_orders
                if order.id not in existing_order_ids
            ]

            if remaining_returns > len(eligible_orders):
                remaining_returns = len(eligible_orders)

            random_generator.shuffle(eligible_orders)

            selected_orders = eligible_orders[:remaining_returns]

            # Retrieve active payment methods.
            payment_methods = session.scalars(
                select(PaymentMethod).where(
                    PaymentMethod.dataset_version_id == version_id,
                    PaymentMethod.is_active.is_(True),
                )
            ).all()

            if not payment_methods:
                raise ValueError(
                    "No active payment methods found."
                )

            # Retrieve existing return numbers.
            existing_return_numbers = set(
                session.scalars(
                    select(SalesReturn.return_number).where(
                        SalesReturn.dataset_version_id == version_id
                    )
                ).all()
            )

            new_returns = 0
            new_return_items = 0
            new_refunds = 0

            return_number = 1

            for order in selected_orders:

                # Retrieve original order items.
                order_items = session.scalars(
                    select(SalesOrderItem).where(
                        SalesOrderItem.dataset_version_id == version_id,
                        SalesOrderItem.order_id == order.id,
                    ).order_by(SalesOrderItem.line_number)
                ).all()

                # Only return items with a positive net value.
                returnable_items = [
                    item
                    for item in order_items
                    if (
                        item.quantity * item.original_unit_price_cents
                        - item.discount_amount_cents
                    ) > 0
                ]

                if not returnable_items:
                    continue

                # Select one or two distinct order items.
                item_count = random_generator.randint(
                    1,
                    min(2, len(returnable_items)),
                )

                selected_items = random_generator.sample(
                    returnable_items,
                    item_count,
                )

                # Generate a return date after the original order date.
                order_date = order.order_date.date()

                maximum_return_date = min(
                    order_date + timedelta(days=30),
                    END_DATE,
                )

                if maximum_return_date <= order_date:
                    continue

                return_date_value = fake.date_between_dates(
                    date_start=order_date + timedelta(days=1),
                    date_end=maximum_return_date,
                )

                return_date = datetime.combine(
                    return_date_value,
                    datetime.min.time(),
                    tzinfo=timezone.utc,
                )

                # Generate return status.
                status = random_generator.choices(
                    [
                        "completed",
                        "approved",
                        "requested",
                        "rejected",
                    ],
                    weights=[75, 10, 10, 5],
                    k=1,
                )[0]

                # Generate a unique return number.
                while (
                    f"RET{return_number:06d}"
                    in existing_return_numbers
                ):
                    return_number += 1

                return_code = f"RET{return_number:06d}"
                return_number += 1

                sales_return = SalesReturn(
                    dataset_version_id=version_id,
                    return_number=return_code,
                    order_id=order.id,
                    return_date=return_date,
                    reason=random_generator.choice(return_reasons),
                    status=status,
                )

                session.add(sales_return)
                session.flush()

                total_return_amount = 0

                # Generate return line items.
                for item in selected_items:

                    return_quantity = random_generator.randint(
                        1,
                        item.quantity,
                    )

                    # Allocate the original line discount
                    # proportionally to the returned quantity.
                    allocated_discount = (
                        item.discount_amount_cents
                        * return_quantity
                        // item.quantity
                    )

                    return_amount = (
                        return_quantity
                        * item.original_unit_price_cents
                        - allocated_discount
                    )

                    return_item = SalesReturnItem(
                        dataset_version_id=version_id,
                        return_id=sales_return.id,
                        order_item_id=item.id,
                        quantity=return_quantity,
                        return_amount_cents=return_amount,
                    )

                    session.add(return_item)

                    total_return_amount += return_amount
                    new_return_items += 1

                # Create refund attempts only for completed returns.
                if status == "completed" and total_return_amount > 0:

                    refund_status = random_generator.choices(
                        [
                            "successful",
                            "pending",
                            "failed",
                        ],
                        weights=[85, 10, 5],
                        k=1,
                    )[0]

                    refund = SalesRefund(
                        dataset_version_id=version_id,
                        return_id=sales_return.id,
                        payment_method_id=(
                            random_generator.choice(payment_methods).id
                        ),
                        refund_reference=f"REF-{return_code}",
                        amount_cents=total_return_amount,
                        status=refund_status,
                        refund_date=return_date,
                    )

                    session.add(refund)
                    new_refunds += 1

                existing_return_numbers.add(return_code)
                new_returns += 1

            session.flush()

            # Retrieve actual database counts.
            total_returns = session.scalar(
                select(func.count()).select_from(SalesReturn).where(
                    SalesReturn.dataset_version_id == version_id
                )
            )

            total_return_items = session.scalar(
                select(func.count()).select_from(SalesReturnItem).where(
                    SalesReturnItem.dataset_version_id == version_id
                )
            )

            total_refunds = session.scalar(
                select(func.count()).select_from(SalesRefund).where(
                    SalesRefund.dataset_version_id == version_id
                )
            )

            result = {
                "dataset_version_id": version_id,
                "new_returns_created": new_returns,
                "new_return_items_created": new_return_items,
                "new_refunds_created": new_refunds,
                "total_sales_returns": total_returns,
                "total_sales_return_items": total_return_items,
                "total_sales_refunds": total_refunds,
            }

    return result


if __name__ == "__main__":
    result = generate_sales_returns()

    print("\nSALES RETURNS AND REFUNDS GENERATION COMPLETED")

    for key, value in result.items():
        print(f"{key}: {value}")
