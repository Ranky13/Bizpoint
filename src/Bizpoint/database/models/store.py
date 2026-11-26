from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKeyConstraint,
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


class Store(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
    Base,
):

    __tablename__ = "stores"

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "store_code",
            name="uq_stores_version_code",
        ),
        UniqueConstraint(
            "dataset_version_id",
            "id",
            name="uq_stores_version_id",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "region_id"],
            ["regions.dataset_version_id", "regions.id"],
            name="fk_stores_region_same_version",
        ),
    )

    store_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    store_code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    region_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )