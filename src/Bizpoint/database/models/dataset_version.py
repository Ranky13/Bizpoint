
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from Bizpoint.database.base import (
    Base,
    UUIDPrimaryKeyMixin,
    TimestampMixin,
)


class DatasetVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):

    __tablename__ = "dataset_versions"

    __table_args__ = (
        UniqueConstraint(
            "dataset_id",
            "version_number",
            name="uq_dataset_versions_dataset_version",
        ),
        CheckConstraint(
            "version_number >= 1",
            name="ck_dataset_versions_positive_number",
        ),
        CheckConstraint(
            "status IN ('draft', 'validated', 'active', 'archived')",
            name="ck_dataset_versions_status",
        ),
        Index(
            "uq_dataset_versions_one_active",
            "dataset_id",
            unique=True,
            sqlite_where=text("status = 'active'"),
            postgresql_where=text("status = 'active'"),
        ),
    )

    dataset_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("datasets.id"),
        nullable=False,
    )

    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
    )

    effective_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    