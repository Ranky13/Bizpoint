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


class GoodsReceipt(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
    Base,
):

    __tablename__ = "goods_receipts"

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "receipt_number",
            name="uq_goods_receipts_version_number",
        ),
        UniqueConstraint(
            "dataset_version_id",
            "id",
            name="uq_goods_receipts_version_id",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "purchase_order_id"],
            ["purchase_orders.dataset_version_id", "purchase_orders.id"],
            name="fk_goods_receipts_purchase_order_same_version",
        ),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected')",
            name="ck_goods_receipts_status",
        ),
    )

    receipt_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    purchase_order_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    received_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
    )