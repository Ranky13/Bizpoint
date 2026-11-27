
from sqlalchemy import (
    CheckConstraint,
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


class FinancialAccount(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
    Base,
):

    __tablename__ = "financial_accounts"

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "account_name",
            name="uq_financial_accounts_version_name",
        ),
        UniqueConstraint(
            "dataset_version_id",
            "account_code",
            name="uq_financial_accounts_version_code",
        ),
        UniqueConstraint(
            "dataset_version_id",
            "id",
            name="uq_financial_accounts_version_id",
        ),
        CheckConstraint(
            "account_type IN ('bank', 'cash', 'payment_processor', 'other')",
            name="ck_financial_accounts_type",
        ),
        CheckConstraint(
            "opening_balance_cents >= 0",
            name="ck_financial_accounts_nonnegative_opening_balance",
        ),
        CheckConstraint(
            "is_active IN (TRUE, FALSE)",
            name="ck_financial_accounts_active",
        ),
    )

    account_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    account_code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    account_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="USD",
    )

    opening_balance_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
    )
