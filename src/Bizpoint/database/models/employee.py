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


class Employee(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
    Base,
):

    __tablename__ = "employees"

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "employee_code",
            name="uq_employees_version_code",
        ),
        UniqueConstraint(
            "dataset_version_id",
            "id",
            name="uq_employees_version_id",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "department_id"],
            ["departments.dataset_version_id", "departments.id"],
            name="fk_employees_department_same_version",
        ),
        CheckConstraint(
            "employment_status IN ('active', 'inactive', 'on_leave', 'terminated')",
            name="ck_employees_employment_status",
        ),
    )

    employee_code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    first_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    last_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    department_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    job_title: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    hire_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    employment_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
    )