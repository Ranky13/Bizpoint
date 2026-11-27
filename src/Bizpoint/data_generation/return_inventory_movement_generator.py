
from sqlalchemy import select, func

from Bizpoint.database.connection import SessionLocal
from Bizpoint.database.models import (
    SalesReturn,
    SalesReturnItem,
    SalesOrder,
    SalesOrderItem,
    InventoryMovement,
)

from Bizpoint.data_generation.config import DATASET_NAME
from Bizpoint.database.models import Dataset, DatasetVersion


def generate_return_inventory_movements():

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

            completed_returns = session.scalars(
                select(SalesReturn).where(
                    SalesReturn.dataset_version_id == version_id,
                    SalesReturn.status == "completed",
                )
            ).all()

            existing_references = set(
                session.scalars(
                    select(InventoryMovement.reference_id).where(
                        InventoryMovement.dataset_version_id == version_id,
                        InventoryMovement.movement_type == "customer_return",
                    )
                ).all()
            )

            new_movements = 0
            skipped_movements = 0

            for sales_return in completed_returns:

                return_items = session.scalars(
                    select(SalesReturnItem).where(
                        SalesReturnItem.dataset_version_id == version_id,
                        SalesReturnItem.return_id == sales_return.id,
                    )
                ).all()

                order = session.get(
                    SalesOrder,
                    sales_return.order_id,
                )

                if order is None:
                    raise ValueError(
                        f"Sales order missing for return {sales_return.return_number}"
                    )

                for return_item in return_items:

                    if return_item.id in existing_references:
                        skipped_movements += 1
                        continue

                    order_item = session.get(
                        SalesOrderItem,
                        return_item.order_item_id,
                    )

                    if order_item is None:
                        raise ValueError(
                            f"Sales order item missing for return item {return_item.id}"
                        )

                    store_id = (
                        order.sales_store_id
                        if order.sales_channel == "physical"
                        else order.fulfillment_store_id
                    )

                    if store_id is None:
                        raise ValueError(
                            f"No inventory store found for return {sales_return.return_number}"
                        )

                    movement = InventoryMovement(
                        dataset_version_id=version_id,
                        product_id=order_item.product_id,
                        store_id=store_id,
                        movement_type="customer_return",
                        quantity=return_item.quantity,
                        unit_cost_cents=order_item.unit_cost_cents,
                        movement_date=sales_return.return_date,
                        reference_id=return_item.id,
                        notes=(
                            f"Inventory returned from "
                            f"{sales_return.return_number}"
                        ),
                    )

                    session.add(movement)
                    existing_references.add(return_item.id)
                    new_movements += 1

            session.flush()

            total_return_movements = session.scalar(
                select(func.count()).select_from(
                    InventoryMovement
                ).where(
                    InventoryMovement.dataset_version_id == version_id,
                    InventoryMovement.movement_type == "customer_return",
                )
            )

    return {
        "dataset_version_id": version_id,
        "new_movements_created": new_movements,
        "existing_movements_skipped": skipped_movements,
        "total_customer_return_movements": total_return_movements,
    }


if __name__ == "__main__":

    result = generate_return_inventory_movements()

    print("\nRETURN INVENTORY MOVEMENT GENERATION COMPLETED")

    for key, value in result.items():
        print(f"{key}: {value}")
