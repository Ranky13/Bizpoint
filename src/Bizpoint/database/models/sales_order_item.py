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


class SalesOrderItem(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
    Base,
):

    __tablename__ = "sales_order_items"

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "id",
            name="uq_sales_order_items_version_id",
        ),
        UniqueConstraint(
            "dataset_version_id",
            "order_id",
            "line_number",
            name="uq_sales_order_items_order_line",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "order_id"],
            ["sales_orders.dataset_version_id", "sales_orders.id"],
            name="fk_sales_order_items_order_same_version",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "product_id"],
            ["products.dataset_version_id", "products.id"],
            name="fk_sales_order_items_product_same_version",
        ),
        CheckConstraint(
            "quantity > 0",
            name="ck_sales_order_items_positive_quantity",
        ),
        CheckConstraint(
            "line_number >= 1",
            name="ck_sales_order_items_positive_line_number",
        ),
        CheckConstraint(
            "original_unit_price_cents >= 0",
            name="ck_sales_order_items_unit_price",
        ),
        CheckConstraint(
            "discount_amount_cents >= 0",
            name="ck_sales_order_items_discount",
        ),
        CheckConstraint(
            "discount_amount_cents <= quantity * original_unit_price_cents",
            name="ck_sales_order_items_discount_limit",
        ),
        CheckConstraint(
            "unit_cost_cents >= 0",
            name="ck_sales_order_items_unit_cost",
        ),
    )

    order_id: Mapped[str] = mapped_column(
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

    original_unit_price_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    discount_amount_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    unit_cost_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )