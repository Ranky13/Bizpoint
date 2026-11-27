
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from Bizpoint.database.base import (
    Base,
    UUIDPrimaryKeyMixin,
)


class AuditLog(
    UUIDPrimaryKeyMixin,
    Base,
):

    __tablename__ = "audit_logs"

    __table_args__ = (
        Index(
            "ix_audit_logs_user_id",
            "user_id",
        ),
        Index(
            "ix_audit_logs_action",
            "action",
        ),
        Index(
            "ix_audit_logs_created_at",
            "created_at",
        ),
    )

    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    entity_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    entity_id: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    old_values: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    new_values: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
