
from sqlalchemy import select, func

from Bizpoint.database.connection import SessionLocal
from Bizpoint.database.models import (
    Dataset,
    DatasetVersion,
    SalesOrder,
    SalesOrderItem,
    InventoryMovement,
)

from Bizpoint.data_generation.config import DATASET_NAME


def generate_sales_inventory_movements():
    """Record inventory consumed by completed sales orders."""

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

            # Retrieve completed sales orders and their items.
            completed_sales = session.execute(
                select(SalesOrder, SalesOrderItem)
                .join(
                    SalesOrderItem,
                    SalesOrderItem.order_id == SalesOrder.id,
                )
                .where(
                    SalesOrder.dataset_version_id == version_id,
                    SalesOrderItem.dataset_version_id == version_id,
                    SalesOrder.status == "completed",
                )
                .order_by(
                    SalesOrder.order_date,
                    SalesOrder.order_number,
                    SalesOrderItem.line_number,
                )
            ).all()

            if not completed_sales:
                raise ValueError(
                    "No completed sales order items found."
                )

            # Retrieve existing sale movement references.
            existing_references = set(
                session.scalars(
                    select(InventoryMovement.reference_id).where(
                        InventoryMovement.dataset_version_id == version_id,
                        InventoryMovement.movement_type == "sale",
                        InventoryMovement.reference_id.is_not(None),
                    )
                ).all()
            )

            new_movements = 0
            skipped_movements = 0

            for order, item in completed_sales:

                # Avoid duplicate movements on reruns.
                if item.id in existing_references:
                    skipped_movements += 1
                    continue

                # Determine the store from which stock was sold.
                if order.sales_channel == "physical":
                    store_id = order.sales_store_id
                elif order.sales_channel == "online":
                    store_id = order.fulfillment_store_id
                else:
                    raise ValueError(
                        f"Invalid sales channel: {order.sales_channel}"
                    )

                if store_id is None:
                    raise ValueError(
                        f"Sales order {order.order_number} "
                        "does not have a valid inventory store."
                    )

                # Create a negative inventory movement.
                movement = InventoryMovement(
                    dataset_version_id=version_id,
                    product_id=item.product_id,
                    store_id=store_id,
                    movement_type="sale",
                    quantity=-item.quantity,
                    unit_cost_cents=item.unit_cost_cents,
                    movement_date=order.order_date,
                    reference_id=item.id,
                    notes=(
                        f"Inventory consumed by sales order "
                        f"{order.order_number}"
                    ),
                )

                session.add(movement)

                existing_references.add(item.id)
                new_movements += 1

            session.flush()

            # Retrieve actual database counts.
            total_sale_movements = session.scalar(
                select(func.count())
                .select_from(InventoryMovement)
                .where(
                    InventoryMovement.dataset_version_id == version_id,
                    InventoryMovement.movement_type == "sale",
                )
            )

            result = {
                "dataset_version_id": version_id,
                "completed_sales_items": len(completed_sales),
                "new_movements_created": new_movements,
                "existing_movements_skipped": skipped_movements,
                "total_sale_movements": total_sale_movements,
            }

    return result


if __name__ == "__main__":
    result = generate_sales_inventory_movements()

    print("\nSALES INVENTORY MOVEMENT GENERATION COMPLETED")

    for key, value in result.items():
        print(f"{key}: {value}")
