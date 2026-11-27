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


class SalesReturn(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
    Base,
):

    __tablename__ = "sales_returns"

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "return_number",
            name="uq_sales_returns_version_number",
        ),
        UniqueConstraint(
            "dataset_version_id",
            "id",
            name="uq_sales_returns_version_id",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "order_id"],
            ["sales_orders.dataset_version_id", "sales_orders.id"],
            name="fk_sales_returns_order_same_version",
        ),
        CheckConstraint(
            "status IN ('requested', 'approved', 'rejected', 'completed')",
            name="ck_sales_returns_status",
        ),
    )

    return_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    order_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    return_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    reason: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="requested",
    )