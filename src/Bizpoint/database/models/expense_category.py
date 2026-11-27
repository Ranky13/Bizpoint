from sqlalchemy import (
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


class ExpenseCategory(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
    Base,
):

    __tablename__ = "expense_categories"

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "category_name",
            name="uq_expense_categories_version_name",
        ),
        UniqueConstraint(
            "dataset_version_id",
            "category_code",
            name="uq_expense_categories_version_code",
        ),
        UniqueConstraint(
            "dataset_version_id",
            "id",
            name="uq_expense_categories_version_id",
        ),
    )

    category_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    category_code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )