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


class SalesPayment(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
    Base,
):

    __tablename__ = "sales_payments"

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "id",
            name="uq_sales_payments_version_id",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "order_id"],
            ["sales_orders.dataset_version_id", "sales_orders.id"],
            name="fk_sales_payments_order_same_version",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "payment_method_id"],
            ["payment_methods.dataset_version_id", "payment_methods.id"],
            name="fk_sales_payments_method_same_version",
        ),
        CheckConstraint(
            "amount_cents > 0",
            name="ck_sales_payments_positive_amount",
        ),
        CheckConstraint(
            "status IN ('pending', 'successful', 'failed', 'reversed')",
            name="ck_sales_payments_status",
        ),
    )

    order_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    payment_method_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    payment_reference: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    amount_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
    )

    payment_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )