from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from Bizpoint.database.base import (
    Base,
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
)


class Department(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
    Base,
):

    __tablename__ = "departments"

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "department_code",
            name="uq_departments_version_code",
        ),
        UniqueConstraint(
            "dataset_version_id",
            "id",
            name="uq_departments_version_id",
        ),
    )

    department_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    department_code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )