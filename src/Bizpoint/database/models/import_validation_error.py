
from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from Bizpoint.database.base import (
    Base,
    UUIDPrimaryKeyMixin,
    TimestampMixin,
)


class ImportValidationError(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    Base,
):

    __tablename__ = "import_validation_errors"

    __table_args__ = (
        CheckConstraint(
            "row_number >= 1",
            name="ck_import_validation_errors_row_number",
        ),
    )

    dataset_import_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("dataset_imports.id"),
        nullable=False,
    )

    row_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    column_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    error_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    error_message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
