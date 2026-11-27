
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


class Budget(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
    Base,
):

    __tablename__ = "budgets"

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "budget_code",
            name="uq_budgets_version_code",
        ),
        UniqueConstraint(
            "dataset_version_id",
            "id",
            name="uq_budgets_version_id",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "expense_category_id"],
            [
                "expense_categories.dataset_version_id",
                "expense_categories.id",
            ],
            name="fk_budgets_category_same_version",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "department_id"],
            [
                "departments.dataset_version_id",
                "departments.id",
            ],
            name="fk_budgets_department_same_version",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "store_id"],
            [
                "stores.dataset_version_id",
                "stores.id",
            ],
            name="fk_budgets_store_same_version",
        ),
        CheckConstraint(
            "budget_amount_cents > 0",
            name="ck_budgets_positive_amount",
        ),
        CheckConstraint(
            "end_date >= start_date",
            name="ck_budgets_valid_date_range",
        ),
        CheckConstraint(
            "status IN ('draft', 'approved', 'closed', 'cancelled')",
            name="ck_budgets_status",
        ),
    )

    budget_code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    budget_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    expense_category_id: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    department_id: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    store_id: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    budget_amount_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    end_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
    )
