
import calendar
import uuid

from collections import defaultdict
from datetime import datetime, time, timezone

from sqlalchemy import select, func

from Bizpoint.database.base import Base
from Bizpoint.database.connection import SessionLocal
import Bizpoint.database.models

from Bizpoint.data_generation.config import (
    DATASET_NAME,
    START_DATE,
    END_DATE,
)
from Bizpoint.data_generation.utils import create_generators


def generate_budgets():

    tables = Base.metadata.tables

    datasets = tables["datasets"]
    versions = tables["dataset_versions"]
    expenses = tables["expenses"]
    categories = tables["expense_categories"]
    budgets = tables["budgets"]

    random_generator, numpy_generator, fake = create_generators()

    with SessionLocal() as session:

        dataset_id = session.scalar(
            select(datasets.c.id).where(
                datasets.c.name == DATASET_NAME
            )
        )

        if not dataset_id:
            raise ValueError("Dataset not found.")

        version_id = session.scalar(
            select(versions.c.id).where(
                versions.c.dataset_id == dataset_id,
                versions.c.version_number == 1,
            )
        )

        if not version_id:
            raise ValueError("Dataset version 1 not found.")

        existing_count = session.scalar(
            select(func.count())
            .select_from(budgets)
            .where(
                budgets.c.dataset_version_id == version_id
            )
        )

        if existing_count:
            print(
                "Budget data already exists. "
                "Skipping generation to prevent duplicates."
            )
            print("Existing budgets:", existing_count)
            return

        category_rows = session.execute(
            select(
                categories.c.id,
                categories.c.category_name,
            ).where(
                categories.c.dataset_version_id == version_id
            )
        ).all()

        category_names = {
            row.id: row.category_name
            for row in category_rows
        }

        expense_rows = session.execute(
            select(
                expenses.c.expense_category_id,
                expenses.c.expense_date,
                expenses.c.amount_cents,
            ).where(
                expenses.c.dataset_version_id == version_id,
                expenses.c.status == "approved",
            )
        ).all()

        # Aggregate approved expenditure by category and month.
        monthly_actuals = defaultdict(int)

        for row in expense_rows:

            expense_date = row.expense_date.date()

            if not START_DATE <= expense_date <= END_DATE:
                continue

            key = (
                row.expense_category_id,
                expense_date.year,
                expense_date.month,
            )

            monthly_actuals[key] += row.amount_cents

        records = []

        for (category_id, year, month), actual_amount in sorted(
            monthly_actuals.items()
        ):

            # Generate a realistic budget around actual expenditure.
            # This permits both overspending and underspending.
            variance_factor = random_generator.uniform(0.90, 1.15)

            budget_amount = max(
                1,
                round(actual_amount * variance_factor),
            )

            month_start = datetime(
                year, month, 1,
                tzinfo=timezone.utc,
            )

            last_day = calendar.monthrange(year, month)[1]

            month_end = datetime(
                year, month, last_day,
                23, 59, 59,
                tzinfo=timezone.utc,
            )

            category_name = category_names[category_id]

            budget_code = (
                f"BUD-{year}{month:02d}-{category_id[:8]}"
            )

            records.append({
                "id": uuid.uuid4().hex,
                "dataset_version_id": version_id,
                "budget_code": budget_code,
                "budget_name": (
                    f"{category_name} Budget - "
                    f"{calendar.month_name[month]} {year}"
                ),
                "description": (
                    "Synthetic historical monthly budget "
                    "based on approved expenditure patterns."
                ),
                "expense_category_id": category_id,
                "department_id": None,
                "store_id": None,
                "budget_amount_cents": budget_amount,
                "start_date": month_start,
                "end_date": month_end,
                "status": "closed",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            })

        if records:
            session.execute(
                budgets.insert(),
                records,
            )

        session.commit()

        total_budget = sum(
            record["budget_amount_cents"]
            for record in records
        )

        print("\nBUDGET GENERATION COMPLETED")
        print("Dataset version:", version_id)
        print("New budgets created:", len(records))
        print("Total budget amount:", f"${total_budget / 100:,.2f}")
        print("Budget status: closed")


if __name__ == "__main__":
    generate_budgets()
