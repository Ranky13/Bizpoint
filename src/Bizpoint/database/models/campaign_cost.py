
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


class CampaignCost(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
    Base,
):

    __tablename__ = "campaign_costs"

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "id",
            name="uq_campaign_costs_version_id",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "campaign_id"],
            [
                "marketing_campaigns.dataset_version_id",
                "marketing_campaigns.id",
            ],
            name="fk_campaign_costs_campaign_same_version",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "expense_id"],
            [
                "expenses.dataset_version_id",
                "expenses.id",
            ],
            name="fk_campaign_costs_expense_same_version",
        ),
        CheckConstraint(
            "amount_cents > 0",
            name="ck_campaign_costs_positive_amount",
        ),
    )

    campaign_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    expense_id: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    cost_reference: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    cost_description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    amount_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    cost_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
