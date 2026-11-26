from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from Bizpoint.database.base import (
    Base,
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
)


class Product(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
    Base,
):

    __tablename__ = "products"

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "sku",
            name="uq_products_version_sku",
        ),
        UniqueConstraint(
            "dataset_version_id",
            "id",
            name="uq_products_version_id",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "category_id"],
            ["product_categories.dataset_version_id", "product_categories.id"],
            name="fk_products_category_same_version",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "brand_id"],
            ["brands.dataset_version_id", "brands.id"],
            name="fk_products_brand_same_version",
        ),
        CheckConstraint(
            "unit_price_cents >= 0",
            name="ck_products_nonnegative_unit_price",
        ),
        CheckConstraint(
            "unit_cost_cents >= 0",
            name="ck_products_nonnegative_unit_cost",
        ),
        CheckConstraint(
            "product_status IN ('active', 'inactive', 'discontinued')",
            name="ck_products_status",
        ),
    )

    sku: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    product_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    category_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    brand_id: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    unit_price_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    unit_cost_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    product_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )