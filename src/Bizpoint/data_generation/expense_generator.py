
import calendar
import random

from datetime import datetime, time

from sqlalchemy import select, func

from Bizpoint.database.connection import SessionLocal
from Bizpoint.database.models import (
    Dataset,
    DatasetVersion,
    Expense,
    ExpenseCategory,
    Department,
    Store,
)

from Bizpoint.data_generation.config import (
    DATASET_NAME,
    START_DATE,
    END_DATE,
    RANDOM_SEED,
)


def generate_expenses():

    rng = random.Random(RANDOM_SEED + 100)

    # Expense amount ranges are in whole USD.
    # Values are converted to integer cents before storage.
    amount_ranges = {
        "RENT": (1500, 4500),
        "SALARIES": (6000, 16000),
        "UTILITIES": (150, 650),
        "TRANSPORT": (200, 1200),
        "MARKETING": (500, 5000),
        "SOFTWARE": (100, 1200),
        "MAINTENANCE": (100, 1800),
        "INSURANCE": (800, 3500),
        "OFFICE_SUPPLIES": (80, 600),
        "PRO_SERVICES": (500, 3000),
        "COMMUNICATION": (60, 250),
        "SECURITY": (250, 700),
        "BANK_CHARGES": (20, 250),
        "MISC": (50, 900),
    }

    descriptions = {
        "RENT": "Monthly premises rental expense",
        "SALARIES": "Monthly departmental payroll expense",
        "UTILITIES": "Electricity and water utility expense",
        "TRANSPORT": "Business transportation and logistics expense",
        "MARKETING": "Advertising and promotional campaign expense",
        "SOFTWARE": "Business software subscription expense",
        "MAINTENANCE": "Facility and equipment maintenance expense",
        "INSURANCE": "Business insurance premium",
        "OFFICE_SUPPLIES": "Office supplies and consumables",
        "PRO_SERVICES": "Professional and consulting services",
        "COMMUNICATION": "Internet and communication expense",
        "SECURITY": "Premises security service expense",
        "BANK_CHARGES": "Banking and transaction charges",
        "MISC": "General operating expense",
    }

    def generate_expense_records(
        categories,
        departments,
        stores,
    ):

        records = []

        category_ids = {
            category.category_code: category.id
            for category in categories
        }

        def add_record(
            expense_date,
            category_code,
            department_id=None,
            store_id=None,
        ):

            minimum, maximum = amount_ranges[category_code]

            amount_cents = rng.randint(
                minimum,
                maximum,
            ) * 100

            day = min(
                expense_date.day,
                calendar.monthrange(
                    expense_date.year,
                    expense_date.month,
                )[1],
            )

            expense_datetime = datetime.combine(
                expense_date.replace(day=day),
                time(hour=12),
            )

            status = rng.choices(
                ["approved", "draft", "rejected", "cancelled"],
                weights=[85, 7, 5, 3],
                k=1,
            )[0]

            records.append({
                "expense_date": expense_datetime,
                "category_code": category_code,
                "department_id": department_id,
                "store_id": store_id,
                "description": descriptions[category_code],
                "amount_cents": amount_cents,
                "status": status,
            })

        # Generate expenses for every month in the reporting period.
        current_year = START_DATE.year
        current_month = START_DATE.month

        while (current_year, current_month) <= (
            END_DATE.year,
            END_DATE.month,
        ):

            month_start = datetime(
                current_year,
                current_month,
                1,
            ).date()

            last_day = calendar.monthrange(
                current_year,
                current_month,
            )[1]

            month_end = datetime(
                current_year,
                current_month,
                last_day,
            ).date()

            # Rent: monthly expense for each store.
            for store in stores:
                add_record(
                    month_start,
                    "RENT",
                    store_id=store.id,
                )

            # Salaries: monthly departmental payroll.
            for department in departments:
                add_record(
                    month_end,
                    "SALARIES",
                    department_id=department.id,
                )

            # Utilities: monthly expense for each store.
            for store in stores:
                add_record(
                    month_start,
                    "UTILITIES",
                    store_id=store.id,
                )

            # Transportation: monthly store-related logistics.
            for store in stores:
                add_record(
                    month_end,
                    "TRANSPORT",
                    store_id=store.id,
                )

            # Communication and security: monthly store expenses.
            for store in stores:
                add_record(
                    month_start,
                    "COMMUNICATION",
                    store_id=store.id,
                )

                add_record(
                    month_start,
                    "SECURITY",
                    store_id=store.id,
                )

            # Software: company-wide monthly subscriptions.
            add_record(
                month_start,
                "SOFTWARE",
            )

            # Marketing: one or two campaigns each month.
            for _ in range(rng.randint(1, 2)):
                add_record(
                    month_end,
                    "MARKETING",
                    department_id=departments[0].id,
                )

            # Office supplies: alternating departmental expenses.
            for department in departments:
                if current_month % 2 == 0:
                    add_record(
                        month_end,
                        "OFFICE_SUPPLIES",
                        department_id=department.id,
                    )

            # Banking charges: monthly company-wide expenses.
            add_record(
                month_end,
                "BANK_CHARGES",
            )

            # Miscellaneous operating expenses.
            add_record(
                month_end,
                "MISC",
            )

            # Quarterly expenses.
            if current_month in (3, 6, 9, 12):

                add_record(
                    month_end,
                    "INSURANCE",
                )

                add_record(
                    month_end,
                    "PRO_SERVICES",
                )

                # Maintenance for selected stores.
                for store in stores:
                    if rng.random() < 0.5:
                        add_record(
                            month_end,
                            "MAINTENANCE",
                            store_id=store.id,
                        )

            # Move to the next month.
            if current_month == 12:
                current_year += 1
                current_month = 1
            else:
                current_month += 1

        # Retain only records within the configured reporting period.
        return [
            record
            for record in records
            if START_DATE <= record["expense_date"].date() <= END_DATE
        ]

    with SessionLocal() as session:

        with session.begin():

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

            categories = session.scalars(
                select(ExpenseCategory).where(
                    ExpenseCategory.dataset_version_id == version_id
                )
            ).all()

            departments = session.scalars(
                select(Department).where(
                    Department.dataset_version_id == version_id
                )
            ).all()

            stores = session.scalars(
                select(Store).where(
                    Store.dataset_version_id == version_id
                )
            ).all()

            category_codes = {
                category.category_code
                for category in categories
            }

            missing_categories = (
                set(amount_ranges.keys()) - category_codes
            )

            if missing_categories:
                raise ValueError(
                    f"Missing expense categories: {missing_categories}"
                )

            if not departments or not stores:
                raise ValueError(
                    "Departments or stores are missing."
                )

            records = generate_expense_records(
                categories,
                departments,
                stores,
            )

            existing_references = set(
                session.scalars(
                    select(Expense.expense_reference).where(
                        Expense.dataset_version_id == version_id
                    )
                ).all()
            )

            new_expenses = 0

            for index, record in enumerate(records, start=1):

                expense_reference = f"EXP-{index:06d}"

                if expense_reference in existing_references:
                    continue

                session.add(
                    Expense(
                        dataset_version_id=version_id,
                        expense_reference=expense_reference,
                        expense_category_id=next(
                            category.id
                            for category in categories
                            if category.category_code
                            == record["category_code"]
                        ),
                        department_id=record["department_id"],
                        store_id=record["store_id"],
                        description=record["description"],
                        amount_cents=record["amount_cents"],
                        expense_date=record["expense_date"],
                        status=record["status"],
                    )
                )

                new_expenses += 1

            session.flush()

            total_expenses = session.scalar(
                select(func.count()).select_from(
                    Expense
                ).where(
                    Expense.dataset_version_id == version_id
                )
            )

            total_amount = session.scalar(
                select(func.coalesce(func.sum(Expense.amount_cents), 0))
                .where(
                    Expense.dataset_version_id == version_id
                )
            )

    return {
        "dataset_version_id": version_id,
        "new_expenses_created": new_expenses,
        "total_expenses": total_expenses,
        "total_expense_amount_cents": total_amount,
    }


if __name__ == "__main__":

    result = generate_expenses()

    print("\nEXPENSE GENERATION COMPLETED")

    for key, value in result.items():
        print(f"{key}: {value}")
