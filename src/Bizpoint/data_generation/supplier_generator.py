
from sqlalchemy import select, func

from Bizpoint.database.connection import SessionLocal
from Bizpoint.database.models import (
    Dataset,
    DatasetVersion,
    Supplier,
)

from Bizpoint.data_generation.config import DATASET_NAME
from Bizpoint.data_generation.utils import create_generators


def generate_suppliers():
    """Generate suppliers for the initial synthetic dataset."""

    random_generator, numpy_generator, fake = create_generators()

    supplier_count = 30

    supplier_names = [
        "Global Trade Supplies",
        "Prime Distribution Group",
        "Evergreen Wholesale",
        "Metro Supply Partners",
        "Universal Goods Limited",
        "Pacific Merchants",
        "Summit Wholesale Group",
        "Atlas Supply Company",
        "Horizon Distribution",
        "Reliable Trade Partners",
        "Bluewave Suppliers",
        "Sterling Goods Company",
        "FirstChoice Distributors",
        "Cornerstone Wholesale",
        "Vertex Supply Solutions",
        "Greenfield Merchants",
        "Pioneer Distribution",
        "Northstar Trading",
        "Goldline Supplies",
        "Brightway Wholesale",
        "Continental Merchants",
        "Silverstone Distributors",
        "Oakwood Supply Group",
        "Redwood Trading Company",
        "PrimeSource Wholesale",
        "Crestview Distributors",
        "Westbridge Supplies",
        "Meridian Trade Group",
        "Summitline Merchants",
        "Corelink Distribution",
    ]

    with SessionLocal() as session:
        with session.begin():

            # Retrieve existing dataset.
            dataset = session.scalar(
                select(Dataset).where(Dataset.name == DATASET_NAME)
            )

            if dataset is None:
                raise ValueError("Dataset does not exist.")

            # Retrieve dataset version.
            version = session.scalar(
                select(DatasetVersion).where(
                    DatasetVersion.dataset_id == dataset.id,
                    DatasetVersion.version_number == 1,
                )
            )

            if version is None:
                raise ValueError("Dataset version 1 does not exist.")

            version_id = version.id

            # Generate suppliers.
            for number in range(1, supplier_count + 1):

                supplier_code = f"SUP{number:04d}"

                existing_supplier = session.scalar(
                    select(Supplier).where(
                        Supplier.dataset_version_id == version_id,
                        Supplier.supplier_code == supplier_code,
                    )
                )

                if existing_supplier is not None:
                    continue

                supplier_name = supplier_names[number - 1]

                supplier = Supplier(
                    dataset_version_id=version_id,
                    supplier_code=supplier_code,
                    supplier_name=supplier_name,
                    contact_person=fake.name(),
                    email=f"supplier{number:04d}@bizpoint.example",
                    phone=f"+1-303-555-{number:04d}",
                    address=fake.address(),
                    status=random_generator.choices(
                        ["active", "inactive"],
                        weights=[90, 10],
                        k=1,
                    )[0],
                )

                session.add(supplier)

            session.flush()

            # Retrieve actual supplier count.
            total_suppliers = session.scalar(
                select(func.count()).select_from(Supplier).where(
                    Supplier.dataset_version_id == version_id
                )
            )

            result = {
                "dataset_version_id": version_id,
                "suppliers": total_suppliers,
            }

    return result


if __name__ == "__main__":
    result = generate_suppliers()

    print("\nSUPPLIER GENERATION COMPLETED")

    for key, value in result.items():
        print(f"{key}: {value}")
