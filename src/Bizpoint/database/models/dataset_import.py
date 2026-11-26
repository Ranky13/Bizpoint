
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from Bizpoint.database.base import (
    Base,
    UUIDPrimaryKeyMixin,
    TimestampMixin,
)


class DatasetImport(UUIDPrimaryKeyMixin, TimestampMixin, Base):

    __tablename__ = "dataset_imports"

    __table_args__ = (
        CheckConstraint(
            "file_format IN ('csv', 'xlsx')",
            name="ck_dataset_imports_file_format",
        ),
        CheckConstraint(
            "status IN ('pending', 'validating', 'validated', 'imported', 'failed')",
            name="ck_dataset_imports_status",
        ),
        CheckConstraint(
            "file_size_bytes >= 0",
            name="ck_dataset_imports_file_size",
        ),
        CheckConstraint(
            "rows_received >= 0 AND rows_accepted >= 0 AND rows_rejected >= 0",
            name="ck_dataset_imports_row_counts",
        ),
    )

    dataset_version_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("dataset_versions.id"),
        nullable=False,
    )

    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    file_format: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
    )

    file_size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    rows_received: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    rows_accepted: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    rows_rejected: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    