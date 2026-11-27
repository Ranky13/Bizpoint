
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
)

from Bizpoint.data_generation.config import DATASET_NAME
from Bizpoint.data_generation.utils import create_generators


def generate_goods_receipts():
    """Generate goods receipts for approved purchase orders."""

    random_generator, numpy_generator, fake = create_generators()

    with SessionLocal() as session:
        with session.begin():

            # Retrieve dataset and version.
            dataset = session.scalar(
                select(Dataset).where(Dataset.name == DATASET_NAME)
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

            # Retrieve approved purchase orders.
            purchase_orders = session.scalars(
                select(PurchaseOrder).where(
                    PurchaseOrder.dataset_version_id == version_id,
                    PurchaseOrder.status == "approved",
                )
            ).all()

            if not purchase_orders:
                raise ValueError("No approved purchase orders found.")

            receipts_created = 0
            receipt_items_created = 0

            for order in purchase_orders:

                # Prevent duplicate receipts if generator is rerun.
                existing_receipt = session.scalar(
                    select(GoodsReceipt.id).where(
                        GoodsReceipt.dataset_version_id == version_id,
                        GoodsReceipt.purchase_order_id == order.id,
                    ).limit(1)
                )

                if existing_receipt is not None:
                    continue

                order_items = session.scalars(
                    select(PurchaseOrderItem).where(
                        PurchaseOrderItem.dataset_version_id == version_id,
                        PurchaseOrderItem.purchase_order_id == order.id,
                    ).order_by(PurchaseOrderItem.line_number)
                ).all()

                if not order_items:
                    continue

                # Some orders have two deliveries.
                has_two_deliveries = (
                    random_generator.random() < 0.45
                )

                delivery_plan = []

                for item in order_items:

                    ordered_quantity = item.quantity

                    if has_two_deliveries:
                        first_quantity = random_generator.randint(
                            max(1, int(ordered_quantity * 0.40)),
                            max(1, int(ordered_quantity * 0.70)),
                        )

                        second_quantity = (
                            ordered_quantity - first_quantity
                        )

                        delivery_plan.append(
                            (item, first_quantity, 1)
                        )

                        delivery_plan.append(
                            (item, second_quantity, 2)
                        )

                    else:
                        # A single partial delivery.
                        received_quantity = random_generator.randint(
                            max(1, int(ordered_quantity * 0.50)),
                            max(1, int(ordered_quantity * 0.85)),
                        )

                        delivery_plan.append(
                            (item, received_quantity, 1)
                        )

                # Create one or two goods receipts.
                delivery_numbers = sorted(
                    set(number for _, _, number in delivery_plan)
                )

                total_quantity_received = 0
                total_quantity_ordered = sum(
                    item.quantity for item in order_items
                )

                for delivery_number in delivery_numbers:

                    receipt_number = (
                        f"GRN-{order.purchase_order_number}-"
                        f"{delivery_number:02d}"
                    )

                    delivery_date = (
                        order.order_date
                        + timedelta(
                            days=random_generator.randint(5, 14)
                            + (delivery_number - 1) * 3
                        )
                    )

                    receipt = GoodsReceipt(
                        dataset_version_id=version_id,
                        receipt_number=receipt_number,
                        purchase_order_id=order.id,
                        received_date=delivery_date,
                        status="accepted",
                    )

                    session.add(receipt)
                    session.flush()

                    receipt_accepted = 0

                    for item, received_quantity, item_delivery in delivery_plan:

                        if item_delivery != delivery_number:
                            continue

                        # Occasionally reject a small quantity.
                        rejected_quantity = 0

                        if (
                            received_quantity >= 5
                            and random_generator.random() < 0.04
                        ):
                            rejected_quantity = 1

                        accepted_quantity = (
                            received_quantity - rejected_quantity
                        )

                        receipt_item = GoodsReceiptItem(
                            dataset_version_id=version_id,
                            goods_receipt_id=receipt.id,
                            purchase_order_item_id=item.id,
                            quantity_received=received_quantity,
                            quantity_accepted=accepted_quantity,
                            quantity_rejected=rejected_quantity,
                            unit_cost_cents=item.unit_cost_cents,
                        )

                        session.add(receipt_item)

                        receipt_accepted += accepted_quantity
                        receipt_items_created += 1

                        total_quantity_received += received_quantity

                    # A receipt is accepted if at least one unit was accepted.
                    # It is rejected only if every received unit was rejected.
                    if receipt_accepted == 0:
                        receipt.status = "rejected"

                    receipts_created += 1

                # Update purchase order delivery status.
                if total_quantity_received >= total_quantity_ordered:
                    order.status = "received"
                elif total_quantity_received > 0:
                    order.status = "partially_received"

            session.flush()

            # Retrieve actual database counts.
            total_receipts = session.scalar(
                select(func.count()).select_from(GoodsReceipt).where(
                    GoodsReceipt.dataset_version_id == version_id
                )
            )

            total_receipt_items = session.scalar(
                select(func.count()).select_from(GoodsReceiptItem).where(
                    GoodsReceiptItem.dataset_version_id == version_id
                )
            )

            result = {
                "dataset_version_id": version_id,
                "new_receipts_created": receipts_created,
                "new_receipt_items_created": receipt_items_created,
                "total_goods_receipts": total_receipts,
                "total_goods_receipt_items": total_receipt_items,
            }

    return result


if __name__ == "__main__":
    result = generate_goods_receipts()

    print("\nGOODS RECEIPT GENERATION COMPLETED")

    for key, value in result.items():
        print(f"{key}: {value}")
