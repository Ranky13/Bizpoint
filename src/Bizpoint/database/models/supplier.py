from sqlalchemy import (
    CheckConstraint,
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


class Supplier(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
    Base,
):

    __tablename__ = "suppliers"

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "supplier_code",
            name="uq_suppliers_version_code",
        ),
        UniqueConstraint(
            "dataset_version_id",
            "id",
            name="uq_suppliers_version_id",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive')",
            name="ck_suppliers_status",
        ),
    )

    supplier_code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    supplier_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    contact_person: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    email: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    phone: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
    )