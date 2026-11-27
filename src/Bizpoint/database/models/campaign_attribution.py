
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


class CampaignAttribution(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    DatasetScopedMixin,
    Base,
):

    __tablename__ = "campaign_attributions"

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "campaign_id",
            "sales_order_id",
            name="uq_campaign_attributions_campaign_order",
        ),
        UniqueConstraint(
            "dataset_version_id",
            "id",
            name="uq_campaign_attributions_version_id",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "campaign_id"],
            [
                "marketing_campaigns.dataset_version_id",
                "marketing_campaigns.id",
            ],
            name="fk_campaign_attributions_campaign_same_version",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "sales_order_id"],
            [
                "sales_orders.dataset_version_id",
                "sales_orders.id",
            ],
            name="fk_campaign_attributions_order_same_version",
        ),
        CheckConstraint(
            "attribution_weight_basis_points > 0 "
            "AND attribution_weight_basis_points <= 10000",
            name="ck_campaign_attributions_valid_weight",
        ),
        CheckConstraint(
            "attribution_model IN ('first_touch', 'last_touch', 'linear', 'position_based')",
            name="ck_campaign_attributions_model",
        ),
    )

    campaign_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    sales_order_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    attribution_model: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    attribution_weight_basis_points: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    attribution_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
