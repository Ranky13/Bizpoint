
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
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


class Expense(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
    Base,
):

    __tablename__ = "expenses"

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "id",
            name="uq_expenses_version_id",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "expense_category_id"],
            [
                "expense_categories.dataset_version_id",
                "expense_categories.id",
            ],
            name="fk_expenses_category_same_version",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "department_id"],
            [
                "departments.dataset_version_id",
                "departments.id",
            ],
            name="fk_expenses_department_same_version",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "store_id"],
            [
                "stores.dataset_version_id",
                "stores.id",
            ],
            name="fk_expenses_store_same_version",
        ),
        CheckConstraint(
            "amount_cents > 0",
            name="ck_expenses_positive_amount",
        ),
        CheckConstraint(
            "status IN ('draft', 'approved', 'rejected', 'cancelled')",
            name="ck_expenses_status",
        ),
    )

    expense_reference: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    expense_category_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    department_id: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    store_id: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    amount_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    expense_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
    )
