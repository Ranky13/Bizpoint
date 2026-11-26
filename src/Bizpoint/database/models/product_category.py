from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from Bizpoint.database.base import (
    Base,
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
)


class ProductCategory(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
    Base,
):

    __tablename__ = "product_categories"

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "category_code",
            name="uq_product_categories_version_code",
        ),
        UniqueConstraint(
            "dataset_version_id",
            "id",
            name="uq_product_categories_version_id",
        ),
    )

    category_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    category_code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )