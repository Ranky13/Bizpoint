
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


class SalesOrderItemTax(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
    Base,
):

    __tablename__ = "sales_order_item_taxes"

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "id",
            name="uq_sales_order_item_taxes_version_id",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "order_item_id"],
            ["sales_order_items.dataset_version_id", "sales_order_items.id"],
            name="fk_order_item_taxes_item_same_version",
        ),
        CheckConstraint(
            "tax_rate_basis_points >= 0 "
            "AND tax_rate_basis_points <= 10000",
            name="ck_order_item_taxes_valid_rate",
        ),
        CheckConstraint(
            "taxable_amount_cents >= 0",
            name="ck_order_item_taxes_taxable_amount",
        ),
        CheckConstraint(
            "tax_amount_cents >= 0",
            name="ck_order_item_taxes_tax_amount",
        ),
        CheckConstraint(
            "tax_amount_cents <= taxable_amount_cents",
            name="ck_order_item_taxes_tax_not_above_taxable_amount",
        ),
    )

    order_item_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    tax_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    tax_rate_basis_points: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    taxable_amount_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    tax_amount_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
