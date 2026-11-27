
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func

from Bizpoint.database.connection import SessionLocal
from Bizpoint.database.models import (
    Dataset,
    DatasetVersion,
    Supplier,
    Store,
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
)

from Bizpoint.data_generation.config import (
    DATASET_NAME,
    START_DATE,
    END_DATE,
)

from Bizpoint.data_generation.utils import create_generators


def generate_purchase_orders():
    """Generate purchase orders and their product line items."""

    random_generator, numpy_generator, fake = create_generators()

    purchase_order_count = 120

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

            # Retrieve existing suppliers, stores and products.
            suppliers = session.scalars(
                select(Supplier).where(
                    Supplier.dataset_version_id == version_id,
                    Supplier.status == "active",
                )
            ).all()

            stores = session.scalars(
                select(Store).where(
                    Store.dataset_version_id == version_id,
                    Store.is_active.is_(True),
                )
            ).all()

            products = session.scalars(
                select(Product).where(
                    Product.dataset_version_id == version_id,
                    Product.product_status == "active",
                    Product.is_active.is_(True),
                )
            ).all()

            if not suppliers:
                raise ValueError("No active suppliers found.")

            if not stores:
                raise ValueError("No active stores found.")

            if len(products) < 5:
                raise ValueError(
                    "At least 5 active products are required."
                )

            # Generate purchase orders.
            for number in range(1, purchase_order_count + 1):

                purchase_order_number = f"PO{number:05d}"

                existing_order = session.scalar(
                    select(PurchaseOrder).where(
                        PurchaseOrder.dataset_version_id == version_id,
                        PurchaseOrder.purchase_order_number
                        == purchase_order_number,
                    )
                )

                if existing_order is not None:
                    continue

                # Generate order date within the dataset period.
                order_date_value = fake.date_between_dates(
                    date_start=START_DATE,
                    date_end=END_DATE,
                )

                order_date = datetime.combine(
                    order_date_value,
                    datetime.min.time(),
                    tzinfo=timezone.utc,
                )

                expected_delivery_date = order_date + timedelta(
                    days=random_generator.randint(5, 21)
                )

                # Keep all generated orders awaiting receipt.
                status = random_generator.choices(
                    ["draft", "submitted", "approved"],
                    weights=[5, 15, 80],
                    k=1,
                )[0]

                purchase_order = PurchaseOrder(
                    dataset_version_id=version_id,
                    purchase_order_number=purchase_order_number,
                    supplier_id=random_generator.choice(suppliers).id,
                    store_id=random_generator.choice(stores).id,
                    order_date=order_date,
                    expected_delivery_date=expected_delivery_date,
                    status=status,
                )

                session.add(purchase_order)
                session.flush()

                # Generate 2–5 distinct product lines per order.
                line_count = random_generator.randint(2, 5)

                selected_products = random_generator.sample(
                    products,
                    line_count,
                )

                for line_number, product in enumerate(
                    selected_products,
                    start=1,
                ):
                    item = PurchaseOrderItem(
                        dataset_version_id=version_id,
                        purchase_order_id=purchase_order.id,
                        product_id=product.id,
                        line_number=line_number,
                        quantity=random_generator.randint(10, 100),
                        unit_cost_cents=product.unit_cost_cents,
                    )

                    session.add(item)

            session.flush()

            # Retrieve actual database counts.
            total_orders = session.scalar(
                select(func.count()).select_from(PurchaseOrder).where(
                    PurchaseOrder.dataset_version_id == version_id
                )
            )

            total_items = session.scalar(
                select(func.count()).select_from(PurchaseOrderItem).where(
                    PurchaseOrderItem.dataset_version_id == version_id
                )
            )

            result = {
                "dataset_version_id": version_id,
                "purchase_orders": total_orders,
                "purchase_order_items": total_items,
            }

    return result


if __name__ == "__main__":
    result = generate_purchase_orders()

    print("\nPURCHASE ORDER GENERATION COMPLETED")

    for key, value in result.items():
        print(f"{key}: {value}")
