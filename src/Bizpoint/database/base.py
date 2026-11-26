from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime, ForeignKey, String



class Base(DeclarativeBase):
    pass

class UUIDPrimaryKeyMixin:
    id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        default=lambda: uuid4().hex,
    )
    
class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class DatasetScopedMixin:

    dataset_version_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("dataset_versions.id"),
        nullable=False,
        index=True,
    )
