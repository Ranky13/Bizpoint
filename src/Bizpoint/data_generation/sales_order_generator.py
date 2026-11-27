
from datetime import datetime, timezone

from sqlalchemy import select, func

from Bizpoint.database.connection import SessionLocal
from Bizpoint.database.models import (
    Dataset,
    DatasetVersion,
    Customer,
    Store,
    Product,
    InventoryMovement,
    SalesOrder,
    SalesOrderItem,
)

from Bizpoint.data_generation.config import (
    DATASET_NAME,
    START_DATE,
    END_DATE,
)

from Bizpoint.data_generation.utils import create_generators


def generate_sales_orders():
    """Generate sales orders and their product line items."""

    random_generator, numpy_generator, fake = create_generators()

    sales_order_count = 1200

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

            # Retrieve existing customers, stores and products.
            customers = session.scalars(
                select(Customer).where(
                    Customer.dataset_version_id == version_id,
                    Customer.status == "active",
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

            if not customers:
                raise ValueError("No active customers found.")

            if not stores:
                raise ValueError("No active stores found.")

            if not products:
                raise ValueError("No active products found.")

            # Retrieve accepted purchase receipt movements.
            receipt_movements = session.scalars(
                select(InventoryMovement)
                .where(
                    InventoryMovement.dataset_version_id == version_id,
                    InventoryMovement.movement_type == "purchase_receipt",
                )
                .order_by(InventoryMovement.movement_date)
            ).all()

            if not receipt_movements:
                raise ValueError(
                    "No purchase receipt inventory movements found."
                )

            # Group receipt events by date.
            receipt_events = {}

            for movement in receipt_movements:
                receipt_date = movement.movement_date.date()

                key = (movement.store_id, movement.product_id)

                receipt_events.setdefault(receipt_date, []).append(
                    (key, movement.quantity)
                )

            receipt_dates = sorted(receipt_events)

            # Generate order dates and process them chronologically.
            order_dates = [
                fake.date_between_dates(
                    date_start=START_DATE,
                    date_end=END_DATE,
                )
                for _ in range(sales_order_count)
            ]

            order_dates.sort()

            # Track stock available for each store-product combination.
            available_stock = {}

            receipt_index = 0

            # Map product IDs to product records.
            product_lookup = {
                product.id: product
                for product in products
            }

            generated_orders = 0

            # Generate sales orders.
            for number, order_date_value in enumerate(
                order_dates,
                start=1,
            ):

                order_number = f"SO{number:06d}"

                existing_order = session.scalar(
                    select(SalesOrder).where(
                        SalesOrder.dataset_version_id == version_id,
                        SalesOrder.order_number == order_number,
                    )
                )

                if existing_order is not None:
                    continue

                order_date = datetime.combine(
                    order_date_value,
                    datetime.min.time(),
                    tzinfo=timezone.utc,
                )

                # Add all stock received on or before this order date.
                while (
                    receipt_index < len(receipt_dates)
                    and receipt_dates[receipt_index] <= order_date_value
                ):
                    receipt_date = receipt_dates[receipt_index]

                    for key, quantity in receipt_events[receipt_date]:
                        available_stock[key] = (
                            available_stock.get(key, 0) + quantity
                        )

                    receipt_index += 1

                # Select a sales channel.
                sales_channel = random_generator.choices(
                    ["physical", "online"],
                    weights=[60, 40],
                    k=1,
                )[0]

                # Physical orders are associated with a sales store.
                # Online orders are fulfilled by one physical store.
                selected_store = random_generator.choice(stores)

                if sales_channel == "physical":
                    sales_store_id = selected_store.id
                    fulfillment_store_id = None
                else:
                    sales_store_id = None
                    fulfillment_store_id = selected_store.id

                stock_store_id = selected_store.id

                # Identify products with available stock at this store.
                available_products = [
                    product
                    for product in products
                    if available_stock.get(
                        (stock_store_id, product.id),
                        0,
                    ) > 0
                ]

                if not available_products:
                    continue

                # Generate 1–4 distinct product lines.
                line_count = random_generator.randint(
                    1,
                    min(4, len(available_products)),
                )

                selected_products = random_generator.sample(
                    available_products,
                    line_count,
                )

                # Generate order status.
                status = random_generator.choices(
                    [
                        "completed",
                        "processing",
                        "pending",
                        "cancelled",
                    ],
                    weights=[80, 10, 5, 5],
                    k=1,
                )[0]

                sales_order = SalesOrder(
                    dataset_version_id=version_id,
                    order_number=order_number,
                    customer_id=random_generator.choice(customers).id,
                    sales_channel=sales_channel,
                    sales_store_id=sales_store_id,
                    fulfillment_store_id=fulfillment_store_id,
                    order_date=order_date,
                    status=status,
                    total_amount_cents=0,
                )

                session.add(sales_order)
                session.flush()

                order_total_cents = 0

                # Generate order line items.
                for line_number, product in enumerate(
                    selected_products,
                    start=1,
                ):

                    stock_key = (stock_store_id, product.id)

                    stock_quantity = available_stock.get(
                        stock_key,
                        0,
                    )

                    if stock_quantity <= 0:
                        continue

                    quantity = random_generator.randint(
                        1,
                        min(5, stock_quantity),
                    )

                    original_unit_price_cents = (
                        product.unit_price_cents
                    )

                    gross_amount_cents = (
                        quantity * original_unit_price_cents
                    )

                    discount_rate = random_generator.uniform(
                        0.00,
                        0.15,
                    )

                    discount_amount_cents = int(
                        gross_amount_cents * discount_rate
                    )

                    unit_cost_cents = product.unit_cost_cents

                    line_total_cents = (
                        gross_amount_cents
                        - discount_amount_cents
                    )

                    item = SalesOrderItem(
                        dataset_version_id=version_id,
                        order_id=sales_order.id,
                        product_id=product.id,
                        line_number=line_number,
                        quantity=quantity,
                        original_unit_price_cents=(
                            original_unit_price_cents
                        ),
                        discount_amount_cents=discount_amount_cents,
                        unit_cost_cents=unit_cost_cents,
                    )

                    session.add(item)

                    order_total_cents += line_total_cents

                    # Only completed orders consume available stock.
                    if status == "completed":
                        available_stock[stock_key] -= quantity

                sales_order.total_amount_cents = order_total_cents

                generated_orders += 1

            session.flush()

            # Retrieve actual database counts.
            total_orders = session.scalar(
                select(func.count()).select_from(SalesOrder).where(
                    SalesOrder.dataset_version_id == version_id
                )
            )

            total_items = session.scalar(
                select(func.count()).select_from(SalesOrderItem).where(
                    SalesOrderItem.dataset_version_id == version_id
                )
            )

            result = {
                "dataset_version_id": version_id,
                "new_orders_generated": generated_orders,
                "total_sales_orders": total_orders,
                "total_sales_order_items": total_items,
            }

    return result


if __name__ == "__main__":
    result = generate_sales_orders()

    print("\nSALES ORDER GENERATION COMPLETED")

    for key, value in result.items():
        print(f"{key}: {value}")
