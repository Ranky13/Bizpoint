
from sqlalchemy import select, func

from Bizpoint.database.connection import SessionLocal
from Bizpoint.database.models import (
    Dataset,
    DatasetVersion,
    ExpenseCategory,
    FinancialAccount,
)

from Bizpoint.data_generation.config import DATASET_NAME


def generate_expense_references():

    categories = [
        ("Rent", "RENT", "Office and store rental expenses."),
        ("Salaries", "SALARIES", "Employee salaries and wages."),
        ("Utilities", "UTILITIES", "Electricity, water and other utilities."),
        ("Transportation", "TRANSPORT", "Business transportation and logistics."),
        ("Marketing", "MARKETING", "Advertising and promotional expenses."),
        ("Software", "SOFTWARE", "Software subscriptions and technology costs."),
        ("Maintenance", "MAINTENANCE", "Equipment and facility maintenance."),
        ("Insurance", "INSURANCE", "Business insurance premiums."),
        ("Office Supplies", "OFFICE_SUPPLIES", "Stationery and office consumables."),
        ("Professional Services", "PRO_SERVICES", "Legal, accounting and consulting services."),
        ("Communication", "COMMUNICATION", "Internet, telephone and communication costs."),
        ("Security", "SECURITY", "Business premises and asset security."),
        ("Bank Charges", "BANK_CHARGES", "Banking and transaction fees."),
        ("Miscellaneous", "MISC", "Other operating expenses."),
    ]

    accounts = [
        {
            "account_name": "Main Operating Bank Account",
            "account_code": "OPERATING_BANK",
            "account_type": "bank",
            "description": "Primary business operating bank account.",
            "currency": "USD",
            "opening_balance_cents": 25000000,
        },
        {
            "account_name": "Business Cash Account",
            "account_code": "BUSINESS_CASH",
            "account_type": "cash",
            "description": "Physical cash held for business transactions.",
            "currency": "USD",
            "opening_balance_cents": 500000,
        },
        {
            "account_name": "Business Savings Account",
            "account_code": "BUSINESS_SAVINGS",
            "account_type": "bank",
            "description": "Business reserve and savings account.",
            "currency": "USD",
            "opening_balance_cents": 10000000,
        },
        {
            "account_name": "Online Payment Processor",
            "account_code": "PAYMENT_PROCESSOR",
            "account_type": "payment_processor",
            "description": "Account representing online payment processor balances.",
            "currency": "USD",
            "opening_balance_cents": 0,
        },
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

            existing_categories = session.scalars(
                select(ExpenseCategory).where(
                    ExpenseCategory.dataset_version_id == version_id
                )
            ).all()

            existing_category_codes = {
                category.category_code
                for category in existing_categories
            }

            existing_accounts = session.scalars(
                select(FinancialAccount).where(
                    FinancialAccount.dataset_version_id == version_id
                )
            ).all()

            existing_account_codes = {
                account.account_code
                for account in existing_accounts
            }

            new_categories = 0
            new_accounts = 0

            for name, code, description in categories:

                if code in existing_category_codes:
                    continue

                session.add(
                    ExpenseCategory(
                        dataset_version_id=version_id,
                        category_name=name,
                        category_code=code,
                        description=description,
                    )
                )

                existing_category_codes.add(code)
                new_categories += 1

            for account in accounts:

                if account["account_code"] in existing_account_codes:
                    continue

                session.add(
                    FinancialAccount(
                        dataset_version_id=version_id,
                        account_name=account["account_name"],
                        account_code=account["account_code"],
                        account_type=account["account_type"],
                        description=account["description"],
                        currency=account["currency"],
                        opening_balance_cents=account["opening_balance_cents"],
                        is_active=True,
                    )
                )

                existing_account_codes.add(account["account_code"])
                new_accounts += 1

            session.flush()

            total_categories = session.scalar(
                select(func.count()).select_from(
                    ExpenseCategory
                ).where(
                    ExpenseCategory.dataset_version_id == version_id
                )
            )

            total_accounts = session.scalar(
                select(func.count()).select_from(
                    FinancialAccount
                ).where(
                    FinancialAccount.dataset_version_id == version_id
                )
            )

    return {
        "dataset_version_id": version_id,
        "new_expense_categories": new_categories,
        "total_expense_categories": total_categories,
        "new_financial_accounts": new_accounts,
        "total_financial_accounts": total_accounts,
    }


if __name__ == "__main__":

    result = generate_expense_references()

    print("\nEXPENSE REFERENCE GENERATION COMPLETED")

    for key, value in result.items():
        print(f"{key}: {value}")
