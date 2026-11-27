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


class InventoryMovement(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
    Base,
):

    __tablename__ = "inventory_movements"

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "id",
            name="uq_inventory_movements_version_id",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "product_id"],
            ["products.dataset_version_id", "products.id"],
            name="fk_inventory_movements_product_same_version",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "store_id"],
            ["stores.dataset_version_id", "stores.id"],
            name="fk_inventory_movements_store_same_version",
        ),
        CheckConstraint(
            "quantity <> 0",
            name="ck_inventory_movements_nonzero_quantity",
        ),
        CheckConstraint(
            "movement_type IN ('opening_stock', 'purchase_receipt', 'sale', 'customer_return', 'write_off', 'adjustment')",
            name="ck_inventory_movements_type",
        ),
        CheckConstraint(
            "unit_cost_cents >= 0",
            name="ck_inventory_movements_nonnegative_cost",
        ),
    )

    product_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    store_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    movement_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    unit_cost_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    movement_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    reference_id: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )