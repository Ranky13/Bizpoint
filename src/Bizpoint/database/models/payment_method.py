from sqlalchemy import Boolean, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from Bizpoint.database.base import (
    Base,
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
)


class PaymentMethod(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
    Base,
):

    __tablename__ = "payment_methods"

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "method_code",
            name="uq_payment_methods_version_code",
        ),
        UniqueConstraint(
            "dataset_version_id",
            "id",
            name="uq_payment_methods_version_id",
        ),
    )

    method_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    method_code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )