from sqlalchemy import select, func

from Bizpoint.database.connection import SessionLocal
from Bizpoint.database.models import Dataset, DatasetVersion, PaymentMethod

from Bizpoint.data_generation.config import DATASET_NAME


def generate_payment_methods():

    payment_methods = [
        {
            "method_name": "Cash",
            "method_code": "CASH",
            "description": "Cash payments received at physical stores.",
        },
        {
            "method_name": "Bank Transfer",
            "method_code": "BANK_TRANSFER",
            "description": "Payments made through bank transfers.",
        },
        {
            "method_name": "Debit Card",
            "method_code": "DEBIT_CARD",
            "description": "Payments made using debit cards.",
        },
        {
            "method_name": "Credit Card",
            "method_code": "CREDIT_CARD",
            "description": "Payments made using credit cards.",
        },
        {
            "method_name": "USSD",
            "method_code": "USSD",
            "description": "Payments made through USSD banking.",
        },
        {
            "method_name": "Mobile Payment",
            "method_code": "MOBILE_PAYMENT",
            "description": "Payments made through mobile payment services.",
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

            existing_methods = session.scalars(
                select(PaymentMethod).where(
                    PaymentMethod.dataset_version_id == version_id
                )
            ).all()

            existing_codes = {
                method.method_code for method in existing_methods
            }

            new_methods = 0

            for method in payment_methods:

                if method["method_code"] in existing_codes:
                    continue

                session.add(
                    PaymentMethod(
                        dataset_version_id=version_id,
                        method_name=method["method_name"],
                        method_code=method["method_code"],
                        description=method["description"],
                        is_active=True,
                    )
                )

                new_methods += 1

            session.flush()

            total_methods = session.scalar(
                select(func.count()).select_from(PaymentMethod).where(
                    PaymentMethod.dataset_version_id == version_id
                )
            )

    return {
        "dataset_version_id": version_id,
        "new_methods_created": new_methods,
        "total_payment_methods": total_methods,
    }


if __name__ == "__main__":

    result = generate_payment_methods()

    print("\nPAYMENT METHOD GENERATION COMPLETED")

    for key, value in result.items():
        print(f"{key}: {value}")