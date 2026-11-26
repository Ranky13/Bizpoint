from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from Bizpoint.database.base import (
    Base,
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
)


class CustomerSegment(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
    Base,
):

    __tablename__ = "customer_segments"

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "segment_code",
            name="uq_customer_segments_version_code",
        ),
        UniqueConstraint(
            "dataset_version_id",
            "id",
            name="uq_customer_segments_version_id",
        ),
    )

    segment_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    segment_code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )