
import random

from datetime import datetime, timedelta, time

from sqlalchemy import select, func

from Bizpoint.database.connection import SessionLocal
from Bizpoint.database.models import (
    Dataset,
    DatasetVersion,
    Expense,
    ExpensePayment,
    FinancialAccount,
)

from Bizpoint.data_generation.config import (
    DATASET_NAME,
    END_DATE,
    RANDOM_SEED,
)


def generate_expense_payments():

    rng = random.Random(RANDOM_SEED + 200)

    payment_statuses = [
        "successful",
        "pending",
        "failed",
        "reversed",
    ]

    payment_weights = [78, 12, 7, 3]

    with SessionLocal() as session:

        with session.begin():

            # Find the existing dataset.
            dataset = session.scalar(
                select(Dataset).where(
                    Dataset.name == DATASET_NAME
                )
            )

            if dataset is None:
                raise ValueError("Dataset does not exist.")

            # Find dataset version 1.
            version = session.scalar(
                select(DatasetVersion).where(
                    DatasetVersion.dataset_id == dataset.id,
                    DatasetVersion.version_number == 1,
                )
            )

            if version is None:
                raise ValueError("Dataset version does not exist.")

            version_id = version.id

            # Retrieve approved expenses.
            approved_expenses = session.scalars(
                select(Expense)
                .where(
                    Expense.dataset_version_id == version_id,
                    Expense.status == "approved",
                )
                .order_by(Expense.expense_reference)
            ).all()

            # Retrieve active financial accounts.
            accounts = session.scalars(
                select(FinancialAccount)
                .where(
                    FinancialAccount.dataset_version_id == version_id,
                    FinancialAccount.is_active.is_(True),
                )
                .order_by(FinancialAccount.account_code)
            ).all()

            if not accounts:
                raise ValueError(
                    "No active financial accounts found."
                )

            # Identify expenses that already have payment records.
            existing_expense_ids = set(
                session.scalars(
                    select(ExpensePayment.expense_id).where(
                        ExpensePayment.dataset_version_id == version_id
                    )
                ).all()
            )

            new_payments = 0

            for expense in approved_expenses:

                # Prevent duplicate payments for the same expense.
                if expense.id in existing_expense_ids:
                    continue

                # Generate a payment amount between 50% and 100%
                # of the approved expense amount.
                minimum_amount = max(
                    1,
                    expense.amount_cents // 2,
                )

                amount_cents = rng.randint(
                    minimum_amount,
                    expense.amount_cents,
                )

                # Select a financial account.
                account = rng.choice(accounts)

                # Generate a payment status.
                payment_status = rng.choices(
                    payment_statuses,
                    weights=payment_weights,
                    k=1,
                )[0]

                # Payment date must not precede the expense date.
                expense_date = expense.expense_date.date()

                days_available = max(
                    0,
                    (END_DATE - expense_date).days,
                )

                payment_delay = rng.randint(
                    0,
                    min(30, days_available),
                )

                payment_date = datetime.combine(
                    expense_date + timedelta(days=payment_delay),
                    time(hour=12),
                )

                payment_reference = (
                    f"EXP-PAY-{expense.expense_reference}"
                )

                session.add(
                    ExpensePayment(
                        dataset_version_id=version_id,
                        payment_reference=payment_reference,
                        expense_id=expense.id,
                        financial_account_id=account.id,
                        amount_cents=amount_cents,
                        payment_date=payment_date,
                        status=payment_status,
                    )
                )

                existing_expense_ids.add(expense.id)
                new_payments += 1

            session.flush()

            # Calculate total payment records.
            total_payments = session.scalar(
                select(func.count()).select_from(
                    ExpensePayment
                ).where(
                    ExpensePayment.dataset_version_id == version_id
                )
            )

            # Count successful payments.
            successful_payments = session.scalar(
                select(func.count()).select_from(
                    ExpensePayment
                ).where(
                    ExpensePayment.dataset_version_id == version_id,
                    ExpensePayment.status == "successful",
                )
            )

            # Calculate actual cash outflow.
            successful_payment_amount = session.scalar(
                select(
                    func.coalesce(
                        func.sum(ExpensePayment.amount_cents),
                        0,
                    )
                ).where(
                    ExpensePayment.dataset_version_id == version_id,
                    ExpensePayment.status == "successful",
                )
            )

            # Count other payment statuses.
            status_counts = {}

            for status in payment_statuses:

                status_counts[status] = session.scalar(
                    select(func.count()).select_from(
                        ExpensePayment
                    ).where(
                        ExpensePayment.dataset_version_id == version_id,
                        ExpensePayment.status == status,
                    )
                )

    return {
        "dataset_version_id": version_id,
        "new_payments_created": new_payments,
        "total_expense_payments": total_payments,
        "successful_payments": status_counts["successful"],
        "pending_payments": status_counts["pending"],
        "failed_payments": status_counts["failed"],
        "reversed_payments": status_counts["reversed"],
        "successful_payment_amount_cents": successful_payment_amount,
    }


if __name__ == "__main__":

    result = generate_expense_payments()

    print("\nEXPENSE PAYMENT GENERATION COMPLETED")

    for key, value in result.items():
        print(f"{key}: {value}")
