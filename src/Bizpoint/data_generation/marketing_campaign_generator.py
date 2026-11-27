
import calendar
import random

from collections import defaultdict
from datetime import datetime, time, timedelta

from sqlalchemy import select, func

from Bizpoint.database.connection import SessionLocal
from Bizpoint.database.models import (
    Dataset,
    DatasetVersion,
    MarketingCampaign,
    CampaignCost,
    CampaignAttribution,
    Expense,
    ExpenseCategory,
    SalesOrder,
)

from Bizpoint.data_generation.config import (
    DATASET_NAME,
    START_DATE,
    END_DATE,
    RANDOM_SEED,
)


def generate_marketing_campaigns():

    rng = random.Random(RANDOM_SEED + 300)

    channels = [
        "social_media",
        "email",
        "search_ads",
        "influencer",
        "offline",
    ]

    campaign_types = [
        "customer_acquisition",
        "customer_retention",
        "brand_awareness",
        "seasonal_promotion",
    ]

    campaign_names = [
        "Customer Acquisition",
        "Customer Retention",
        "Brand Awareness",
        "Seasonal Promotion",
        "Product Promotion",
        "Sales Growth",
    ]

    with SessionLocal() as session:

        with session.begin():

            # -------------------------------------------------
            # 1. Retrieve dataset and version.
            # -------------------------------------------------

            dataset = session.scalar(
                select(Dataset).where(
                    Dataset.name == DATASET_NAME
                )
            )

            if dataset is None:
                raise ValueError("Dataset does not exist.")

            version = session.scalar(
                select(DatasetVersion).where(
                    DatasetVersion.dataset_id == dataset.id,
                    DatasetVersion.version_number == 1,
                )
            )

            if version is None:
                raise ValueError("Dataset version does not exist.")

            version_id = version.id

            # -------------------------------------------------
            # 2. Prevent duplicate campaign generation.
            # -------------------------------------------------

            existing_campaign_count = session.scalar(
                select(func.count()).select_from(
                    MarketingCampaign
                ).where(
                    MarketingCampaign.dataset_version_id == version_id
                )
            )

            existing_cost_count = session.scalar(
                select(func.count()).select_from(
                    CampaignCost
                ).where(
                    CampaignCost.dataset_version_id == version_id
                )
            )

            existing_attribution_count = session.scalar(
                select(func.count()).select_from(
                    CampaignAttribution
                ).where(
                    CampaignAttribution.dataset_version_id == version_id
                )
            )

            if (
                existing_campaign_count
                or existing_cost_count
                or existing_attribution_count
            ):
                print(
                    "Marketing data already exists. "
                    "Skipping generation to prevent duplicates."
                )

                return {
                    "dataset_version_id": version_id,
                    "new_campaigns_created": 0,
                    "new_campaign_costs_created": 0,
                    "new_attributions_created": 0,
                    "existing_campaigns": existing_campaign_count,
                    "existing_campaign_costs": existing_cost_count,
                    "existing_attributions": existing_attribution_count,
                }

            # -------------------------------------------------
            # 3. Retrieve the marketing expense category.
            # -------------------------------------------------

            marketing_category = session.scalar(
                select(ExpenseCategory).where(
                    ExpenseCategory.dataset_version_id == version_id,
                    ExpenseCategory.category_code == "MARKETING",
                )
            )

            if marketing_category is None:
                raise ValueError(
                    "Marketing expense category does not exist."
                )

            # -------------------------------------------------
            # 4. Retrieve approved marketing expenses.
            # -------------------------------------------------

            marketing_expenses = session.scalars(
                select(Expense)
                .where(
                    Expense.dataset_version_id == version_id,
                    Expense.expense_category_id == marketing_category.id,
                    Expense.status == "approved",
                )
                .order_by(Expense.expense_date)
            ).all()

            if not marketing_expenses:
                raise ValueError(
                    "No approved marketing expenses found."
                )

            # -------------------------------------------------
            # 5. Retrieve completed sales orders.
            # -------------------------------------------------

            completed_orders = session.scalars(
                select(SalesOrder)
                .where(
                    SalesOrder.dataset_version_id == version_id,
                    SalesOrder.status == "completed",
                )
                .order_by(SalesOrder.order_date)
            ).all()

            # -------------------------------------------------
            # 6. Group marketing expenses by reporting month.
            # -------------------------------------------------

            expenses_by_month = defaultdict(list)

            for expense in marketing_expenses:

                expense_date = expense.expense_date.date()

                month_key = (
                    expense_date.year,
                    expense_date.month,
                )

                expenses_by_month[month_key].append(expense)

            # Group completed sales orders by month.
            orders_by_month = defaultdict(list)

            for order in completed_orders:

                order_date = order.order_date.date()

                month_key = (
                    order_date.year,
                    order_date.month,
                )

                orders_by_month[month_key].append(order)

            # -------------------------------------------------
            # 7. Create monthly marketing campaigns.
            # -------------------------------------------------

            campaign_by_month = {}

            campaigns_created = 0

            for year, month in sorted(expenses_by_month):

                month_start = datetime(
                    year,
                    month,
                    1,
                    0,
                    0,
                )

                last_day = calendar.monthrange(
                    year,
                    month,
                )[1]

                month_end = datetime(
                    year,
                    month,
                    last_day,
                    23,
                    59,
                    59,
                )

                campaign_code = (
                    f"MKT-{year}-{month:02d}"
                )

                campaign_type = rng.choice(
                    campaign_types
                )

                campaign_channel = rng.choice(
                    channels
                )

                campaign_name = (
                    f"{calendar.month_name[month]} "
                    f"{year} "
                    f"{rng.choice(campaign_names)} Campaign"
                )

                campaign = MarketingCampaign(
                    dataset_version_id=version_id,
                    campaign_code=campaign_code,
                    campaign_name=campaign_name,
                    campaign_type=campaign_type,
                    marketing_channel=campaign_channel,
                    description=(
                        f"Synthetic {campaign_type.replace('_', ' ')} "
                        f"campaign conducted through "
                        f"{campaign_channel.replace('_', ' ')} "
                        f"during {calendar.month_name[month]} {year}."
                    ),
                    start_date=month_start,
                    end_date=month_end,
                    status="completed",
                )

                session.add(campaign)

                campaign_by_month[(year, month)] = campaign

                campaigns_created += 1

            session.flush()

            # -------------------------------------------------
            # 8. Link approved expenses to campaign costs.
            # -------------------------------------------------

            costs_created = 0
            total_campaign_cost_cents = 0

            for month_key, expenses in expenses_by_month.items():

                campaign = campaign_by_month[month_key]

                for expense in expenses:

                    cost = CampaignCost(
                        dataset_version_id=version_id,
                        campaign_id=campaign.id,
                        expense_id=expense.id,
                        cost_reference=(
                            f"MKT-COST-{expense.expense_reference}"
                        ),
                        cost_description=expense.description,
                        amount_cents=expense.amount_cents,
                        cost_date=expense.expense_date,
                    )

                    session.add(cost)

                    costs_created += 1

                    total_campaign_cost_cents += (
                        expense.amount_cents
                    )

            session.flush()

            # -------------------------------------------------
            # 9. Generate last-touch sales attribution.
            # -------------------------------------------------

            attributions_created = 0

            for month_key, campaign in campaign_by_month.items():

                eligible_orders = orders_by_month.get(
                    month_key,
                    [],
                )

                if not eligible_orders:
                    continue

                # Attribute approximately 20% of eligible
                # completed orders to this campaign.
                # At least one order is selected when possible.
                sample_size = max(
                    1,
                    round(len(eligible_orders) * 0.20),
                )

                sample_size = min(
                    sample_size,
                    len(eligible_orders),
                )

                selected_orders = rng.sample(
                    eligible_orders,
                    sample_size,
                )

                for order in selected_orders:

                    order_date = order.order_date.date()

                    campaign_start = datetime(
                        month_key[0],
                        month_key[1],
                        1,
                    ).date()

                    available_days = max(
                        0,
                        (order_date - campaign_start).days,
                    )

                    # Interaction must occur on or before
                    # the attributed order date.
                    interaction_delay = rng.randint(
                        0,
                        min(14, available_days),
                    )

                    attribution_date = datetime.combine(
                        order_date - timedelta(
                            days=interaction_delay
                        ),
                        time(hour=12),
                    )

                    attribution = CampaignAttribution(
                        dataset_version_id=version_id,
                        campaign_id=campaign.id,
                        sales_order_id=order.id,
                        attribution_model="last_touch",
                        attribution_weight_basis_points=10000,
                        attribution_date=attribution_date,
                    )

                    session.add(attribution)

                    attributions_created += 1

            session.flush()

            # -------------------------------------------------
            # 10. Calculate generation totals.
            # -------------------------------------------------

            total_campaigns = session.scalar(
                select(func.count()).select_from(
                    MarketingCampaign
                ).where(
                    MarketingCampaign.dataset_version_id == version_id
                )
            )

            total_costs = session.scalar(
                select(func.count()).select_from(
                    CampaignCost
                ).where(
                    CampaignCost.dataset_version_id == version_id
                )
            )

            total_attributions = session.scalar(
                select(func.count()).select_from(
                    CampaignAttribution
                ).where(
                    CampaignAttribution.dataset_version_id == version_id
                )
            )

    return {
        "dataset_version_id": version_id,
        "new_campaigns_created": campaigns_created,
        "total_campaigns": total_campaigns,
        "new_campaign_costs_created": costs_created,
        "total_campaign_costs": total_costs,
        "total_campaign_cost_amount_cents": (
            total_campaign_cost_cents
        ),
        "new_attributions_created": attributions_created,
        "total_campaign_attributions": total_attributions,
    }


if __name__ == "__main__":

    result = generate_marketing_campaigns()

    print("\nMARKETING CAMPAIGN GENERATION COMPLETED")

    for key, value in result.items():
        print(f"{key}: {value}")
