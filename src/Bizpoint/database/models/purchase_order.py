from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
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


class PurchaseOrder(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
    Base,
):

    __tablename__ = "purchase_orders"

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "purchase_order_number",
            name="uq_purchase_orders_version_number",
        ),
        UniqueConstraint(
            "dataset_version_id",
            "id",
            name="uq_purchase_orders_version_id",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "supplier_id"],
            ["suppliers.dataset_version_id", "suppliers.id"],
            name="fk_purchase_orders_supplier_same_version",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "store_id"],
            ["stores.dataset_version_id", "stores.id"],
            name="fk_purchase_orders_store_same_version",
        ),
        CheckConstraint(
            "status IN ('draft', 'submitted', 'approved', 'partially_received', 'received', 'cancelled')",
            name="ck_purchase_orders_status",
        ),
    )

    purchase_order_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    supplier_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    store_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    order_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    expected_delivery_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="draft",
    )