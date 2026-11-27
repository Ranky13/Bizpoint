
from sqlalchemy import select, func

from Bizpoint.database.connection import SessionLocal
from Bizpoint.database.models import (
    Dataset,
    DatasetVersion,
    GoodsReceipt,
    GoodsReceiptItem,
    PurchaseOrder,
    PurchaseOrderItem,
    InventoryMovement,
)

from Bizpoint.data_generation.config import DATASET_NAME


def generate_inventory_movements():
    """Create inventory movements from accepted goods receipt quantities."""

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

            # Retrieve accepted receipt items and their related records.
            receipt_records = session.execute(
                select(
                    GoodsReceiptItem,
                    GoodsReceipt,
                    PurchaseOrderItem,
                    PurchaseOrder,
                )
                .join(
                    GoodsReceipt,
                    GoodsReceiptItem.goods_receipt_id == GoodsReceipt.id,
                )
                .join(
                    PurchaseOrderItem,
                    GoodsReceiptItem.purchase_order_item_id
                    == PurchaseOrderItem.id,
                )
                .join(
                    PurchaseOrder,
                    GoodsReceipt.purchase_order_id == PurchaseOrder.id,
                )
                .where(
                    GoodsReceiptItem.dataset_version_id == version_id,
                    GoodsReceipt.dataset_version_id == version_id,
                    PurchaseOrderItem.dataset_version_id == version_id,
                    PurchaseOrder.dataset_version_id == version_id,
                    GoodsReceipt.status == "accepted",
                )
            ).all()

            if not receipt_records:
                raise ValueError("No accepted goods receipt items found.")

            new_movements = 0

            for receipt_item, receipt, order_item, order in receipt_records:

                accepted_quantity = receipt_item.quantity_accepted

                # Rejected quantities must never enter inventory.
                if accepted_quantity <= 0:
                    continue

                # Prevent duplicate movements on reruns.
                existing_movement = session.scalar(
                    select(InventoryMovement.id).where(
                        InventoryMovement.dataset_version_id == version_id,
                        InventoryMovement.movement_type == "purchase_receipt",
                        InventoryMovement.reference_id == receipt_item.id,
                    ).limit(1)
                )

                if existing_movement is not None:
                    continue

                movement = InventoryMovement(
                    dataset_version_id=version_id,
                    product_id=order_item.product_id,
                    store_id=order.store_id,
                    movement_type="purchase_receipt",
                    quantity=accepted_quantity,
                    unit_cost_cents=receipt_item.unit_cost_cents,
                    movement_date=receipt.received_date,
                    reference_id=receipt_item.id,
                    notes=(
                        f"Accepted goods receipt: {receipt.receipt_number}"
                    ),
                )

                session.add(movement)
                new_movements += 1

            session.flush()

            # Calculate actual inventory movement totals.
            total_movements = session.scalar(
                select(func.count()).select_from(InventoryMovement).where(
                    InventoryMovement.dataset_version_id == version_id,
                    InventoryMovement.movement_type == "purchase_receipt",
                )
            )

            total_units_received = session.scalar(
                select(
                    func.coalesce(func.sum(InventoryMovement.quantity), 0)
                ).where(
                    InventoryMovement.dataset_version_id == version_id,
                    InventoryMovement.movement_type == "purchase_receipt",
                )
            )

            result = {
                "dataset_version_id": version_id,
                "new_movements_created": new_movements,
                "total_purchase_receipt_movements": total_movements,
                "total_accepted_units_added": total_units_received,
            }

    return result


if __name__ == "__main__":
    result = generate_inventory_movements()

    print("\nINVENTORY MOVEMENT GENERATION COMPLETED")

    for key, value in result.items():
        print(f"{key}: {value}")

