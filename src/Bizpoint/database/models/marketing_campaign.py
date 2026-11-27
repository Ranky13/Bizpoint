
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
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


class MarketingCampaign(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
    Base,
):

    __tablename__ = "marketing_campaigns"

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "campaign_code",
            name="uq_marketing_campaigns_version_code",
        ),
        UniqueConstraint(
            "dataset_version_id",
            "id",
            name="uq_marketing_campaigns_version_id",
        ),
        CheckConstraint(
            "status IN ('draft', 'planned', 'active', 'completed', 'cancelled')",
            name="ck_marketing_campaigns_status",
        ),
        CheckConstraint(
            "end_date >= start_date",
            name="ck_marketing_campaigns_valid_date_range",
        ),
    )

    campaign_code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    campaign_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    campaign_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    marketing_channel: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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
        default="planned",
    )
