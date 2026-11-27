
from sqlalchemy import CheckConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from Bizpoint.database.base import (
    Base,
    UUIDPrimaryKeyMixin,
    TimestampMixin,
)


class Dataset(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    Base,
):

    __tablename__ = "datasets"

    __table_args__ = (
        CheckConstraint(
            "source_type IN ('synthetic', 'imported')",
            name="ck_datasets_source_type",
        ),
        CheckConstraint(
            "status IN ('active', 'archived')",
            name="ck_datasets_status",
        ),
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    source_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="synthetic",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
    )
