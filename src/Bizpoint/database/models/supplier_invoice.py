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


class SupplierInvoice(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
    Base,
):

    __tablename__ = "supplier_invoices"

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "supplier_id",
            "invoice_number",
            name="uq_supplier_invoices_supplier_number",
        ),
        UniqueConstraint(
            "dataset_version_id",
            "id",
            name="uq_supplier_invoices_version_id",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "supplier_id"],
            ["suppliers.dataset_version_id", "suppliers.id"],
            name="fk_supplier_invoices_supplier_same_version",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "purchase_order_id"],
            ["purchase_orders.dataset_version_id", "purchase_orders.id"],
            name="fk_supplier_invoices_purchase_order_same_version",
        ),
        CheckConstraint(
            "invoice_amount_cents > 0",
            name="ck_supplier_invoices_positive_amount",
        ),
        CheckConstraint(
            "status IN ('draft', 'submitted', 'approved', 'disputed', 'cancelled')",
            name="ck_supplier_invoices_status",
        ),
    )

    invoice_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    supplier_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    purchase_order_id: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    invoice_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    due_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    invoice_amount_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
    )