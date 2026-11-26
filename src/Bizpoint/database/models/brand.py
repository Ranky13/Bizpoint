from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from Bizpoint.database.base import (
    Base,
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
)


class Brand(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
    Base,
):

    __tablename__ = "brands"

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "brand_code",
            name="uq_brands_version_code",
        ),
        UniqueConstraint(
            "dataset_version_id",
            "id",
            name="uq_brands_version_id",
        ),
    )

    brand_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    brand_code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )