
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
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


class ExpensePayment(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
    Base,
):

    __tablename__ = "expense_payments"

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "id",
            name="uq_expense_payments_version_id",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "expense_id"],
            [
                "expenses.dataset_version_id",
                "expenses.id",
            ],
            name="fk_expense_payments_expense_same_version",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "financial_account_id"],
            [
                "financial_accounts.dataset_version_id",
                "financial_accounts.id",
            ],
            name="fk_expense_payments_account_same_version",
        ),
        CheckConstraint(
            "amount_cents > 0",
            name="ck_expense_payments_positive_amount",
        ),
        CheckConstraint(
            "status IN ('pending', 'successful', 'failed', 'reversed')",
            name="ck_expense_payments_status",
        ),
    )

    payment_reference: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    expense_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    financial_account_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    amount_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    payment_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
    )

