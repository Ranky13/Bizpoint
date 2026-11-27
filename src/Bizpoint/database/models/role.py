
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
)


class Role(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    Base,
):

    __tablename__ = "roles"

    __table_args__ = (
        UniqueConstraint(
            "role_name",
            name="uq_roles_name",
        ),
        UniqueConstraint(
            "role_code",
            name="uq_roles_code",
        ),
    )

    role_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    role_code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
