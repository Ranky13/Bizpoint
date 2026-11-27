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


class GoodsReceiptItem(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
    Base,
):

    __tablename__ = "goods_receipt_items"

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "id",
            name="uq_goods_receipt_items_version_id",
        ),
        UniqueConstraint(
            "dataset_version_id",
            "goods_receipt_id",
            "purchase_order_item_id",
            name="uq_goods_receipt_items_receipt_order_item",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "goods_receipt_id"],
            ["goods_receipts.dataset_version_id", "goods_receipts.id"],
            name="fk_goods_receipt_items_receipt_same_version",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "purchase_order_item_id"],
            ["purchase_order_items.dataset_version_id", "purchase_order_items.id"],
            name="fk_goods_receipt_items_order_item_same_version",
        ),
        CheckConstraint(
            "quantity_received > 0",
            name="ck_goods_receipt_items_positive_received",
        ),
        CheckConstraint(
            "quantity_accepted >= 0",
            name="ck_goods_receipt_items_nonnegative_accepted",
        ),
        CheckConstraint(
            "quantity_rejected >= 0",
            name="ck_goods_receipt_items_nonnegative_rejected",
        ),
        CheckConstraint(
            "quantity_received = quantity_accepted + quantity_rejected",
            name="ck_goods_receipt_items_quantity_reconciliation",
        ),
        CheckConstraint(
            "unit_cost_cents >= 0",
            name="ck_goods_receipt_items_nonnegative_cost",
        ),
    )

    goods_receipt_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    purchase_order_item_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    quantity_received: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    quantity_accepted: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    quantity_rejected: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    unit_cost_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )