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


class SalesReturnItem(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
    Base,
):

    __tablename__ = "sales_return_items"

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "id",
            name="uq_sales_return_items_version_id",
        ),
        UniqueConstraint(
            "dataset_version_id",
            "return_id",
            "order_item_id",
            name="uq_sales_return_items_return_order_item",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "return_id"],
            ["sales_returns.dataset_version_id", "sales_returns.id"],
            name="fk_sales_return_items_return_same_version",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "order_item_id"],
            ["sales_order_items.dataset_version_id", "sales_order_items.id"],
            name="fk_sales_return_items_order_item_same_version",
        ),
        CheckConstraint(
            "quantity > 0",
            name="ck_sales_return_items_positive_quantity",
        ),
        CheckConstraint(
            "return_amount_cents >= 0",
            name="ck_sales_return_items_nonnegative_amount",
        ),
    )

    return_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    order_item_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    return_amount_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )