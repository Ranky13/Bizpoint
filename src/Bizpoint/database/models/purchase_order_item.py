from sqlalchemy import (
    CheckConstraint,
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


class PurchaseOrderItem(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
    Base,
):

    __tablename__ = "purchase_order_items"

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "id",
            name="uq_purchase_order_items_version_id",
        ),
        UniqueConstraint(
            "dataset_version_id",
            "purchase_order_id",
            "line_number",
            name="uq_purchase_order_items_line",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "purchase_order_id"],
            ["purchase_orders.dataset_version_id", "purchase_orders.id"],
            name="fk_purchase_order_items_order_same_version",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "product_id"],
            ["products.dataset_version_id", "products.id"],
            name="fk_purchase_order_items_product_same_version",
        ),
        CheckConstraint(
            "line_number >= 1",
            name="ck_purchase_order_items_positive_line",
        ),
        CheckConstraint(
            "quantity > 0",
            name="ck_purchase_order_items_positive_quantity",
        ),
        CheckConstraint(
            "unit_cost_cents >= 0",
            name="ck_purchase_order_items_nonnegative_cost",
        ),
    )

    purchase_order_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    product_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    line_number: Mapped[int] = mapped_column(
        Integer,
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