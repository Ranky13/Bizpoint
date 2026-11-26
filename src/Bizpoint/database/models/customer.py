from datetime import date

from sqlalchemy import (
    CheckConstraint,
    Date,
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


class Customer(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
    Base,
):

    __tablename__ = "customers"

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "customer_code",
            name="uq_customers_version_code",
        ),
        UniqueConstraint(
            "dataset_version_id",
            "id",
            name="uq_customers_version_id",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "region_id"],
            ["regions.dataset_version_id", "regions.id"],
            name="fk_customers_region_same_version",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "segment_id"],
            ["customer_segments.dataset_version_id", "customer_segments.id"],
            name="fk_customers_segment_same_version",
        ),
        CheckConstraint(
            "customer_type IN ('individual', 'business')",
            name="ck_customers_customer_type",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive', 'blocked')",
            name="ck_customers_status",
        ),
    )

    customer_code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    first_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    last_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    business_name: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    customer_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="individual",
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    phone: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    region_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    segment_id: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    registration_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
    )