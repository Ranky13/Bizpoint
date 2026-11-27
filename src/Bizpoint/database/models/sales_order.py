
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from Bizpoint.database.base import (
    Base,
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
)


class SalesOrder(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
    Base,
):

    __tablename__ = "sales_orders"

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "order_number",
            name="uq_sales_orders_version_number",
        ),
        UniqueConstraint(
            "dataset_version_id",
            "id",
            name="uq_sales_orders_version_id",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "customer_id"],
            ["customers.dataset_version_id", "customers.id"],
            name="fk_sales_orders_customer_same_version",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "sales_store_id"],
            ["stores.dataset_version_id", "stores.id"],
            name="fk_sales_orders_sales_store_same_version",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "fulfillment_store_id"],
            ["stores.dataset_version_id", "stores.id"],
            name="fk_sales_orders_fulfillment_store_same_version",
        ),
        CheckConstraint(
            "sales_channel IN ('physical', 'online')",
            name="ck_sales_orders_channel",
        ),
        CheckConstraint(
            """
            (
                sales_channel = 'physical'
                AND sales_store_id IS NOT NULL
                AND fulfillment_store_id IS NULL
            )
            OR
            (
                sales_channel = 'online'
                AND sales_store_id IS NULL
            )
            """,
            name="ck_sales_orders_channel_store_consistency",
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'cancelled')",
            name="ck_sales_orders_status",
        ),
        CheckConstraint(
            "total_amount_cents >= 0",
            name="ck_sales_orders_total_amount",
        ),
    )

    order_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    customer_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    sales_channel: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    sales_store_id: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    fulfillment_store_id: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    order_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
    )

    total_amount_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
