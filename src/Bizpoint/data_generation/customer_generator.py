
from sqlalchemy import select, func

from Bizpoint.database.connection import SessionLocal
from Bizpoint.database.models import (
    Dataset,
    DatasetVersion,
    Region,
    CustomerSegment,
    Customer,
)

from Bizpoint.data_generation.config import (
    DATASET_NAME,
    START_DATE,
    END_DATE,
)

from Bizpoint.data_generation.utils import create_generators


def generate_customers():
    """Generate customer segments and customers for dataset version 1."""

    random_generator, numpy_generator, fake = create_generators()

    segment_data = [
        ("Premium", "PREM", "High-value customers with strong purchasing activity"),
        ("Regular", "REG", "Customers with consistent purchasing activity"),
        ("New", "NEW", "Recently registered customers"),
        ("Wholesale", "WHOLE", "Customers purchasing goods in bulk"),
        ("Occasional", "OCC", "Customers with infrequent purchasing activity"),
    ]

    customer_count = 500

    with SessionLocal() as session:
        with session.begin():

            # Retrieve the existing dataset and version.
            dataset = session.scalar(
                select(Dataset).where(Dataset.name == DATASET_NAME)
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
                raise ValueError("Dataset version 1 does not exist.")

            version_id = version.id

            # Retrieve existing regions.
            regions = session.scalars(
                select(Region).where(
                    Region.dataset_version_id == version_id
                )
            ).all()

            if not regions:
                raise ValueError(
                    "No regions found. Run organization_generator first."
                )

            # Create customer segments.
            segments = {}

            for name, code, description in segment_data:

                segment = session.scalar(
                    select(CustomerSegment).where(
                        CustomerSegment.dataset_version_id == version_id,
                        CustomerSegment.segment_code == code,
                    )
                )

                if segment is None:
                    segment = CustomerSegment(
                        dataset_version_id=version_id,
                        segment_name=name,
                        segment_code=code,
                        description=description,
                    )
                    session.add(segment)
                    session.flush()

                segments[code] = segment

            print("CUSTOMER SEGMENTS:", len(segments))

            # Generate customers.
            segment_codes = list(segments.keys())

            for number in range(1, customer_count + 1):

                customer_code = f"CUS{number:05d}"

                existing_customer = session.scalar(
                    select(Customer).where(
                        Customer.dataset_version_id == version_id,
                        Customer.customer_code == customer_code,
                    )
                )

                if existing_customer is not None:
                    continue

                customer_type = random_generator.choices(
                    ["individual", "business"],
                    weights=[80, 20],
                    k=1,
                )[0]

                if customer_type == "individual":
                    first_name = fake.first_name()
                    last_name = fake.last_name()
                    business_name = None
                else:
                    first_name = None
                    last_name = None
                    business_name = fake.company()

                customer = Customer(
                    dataset_version_id=version_id,
                    customer_code=customer_code,
                    first_name=first_name,
                    last_name=last_name,
                    business_name=business_name,
                    customer_type=customer_type,
                    email=f"customer{number:05d}@bizpoint.example",
                    phone=f"+1-202-555-{number:04d}",
                    region_id=random_generator.choice(regions).id,
                    segment_id=segments[
                        random_generator.choice(segment_codes)
                    ].id,
                    registration_date=fake.date_between_dates(
                        date_start=START_DATE,
                        date_end=END_DATE,
                    ),
                    status=random_generator.choices(
                        ["active", "inactive", "blocked"],
                        weights=[88, 9, 3],
                        k=1,
                    )[0],
                )

                session.add(customer)

            session.flush()

            # Obtain actual database counts.
            total_customers = session.scalar(
                select(func.count()).select_from(Customer).where(
                    Customer.dataset_version_id == version_id
                )
            )

            total_segments = session.scalar(
                select(func.count()).select_from(CustomerSegment).where(
                    CustomerSegment.dataset_version_id == version_id
                )
            )

            result = {
                "dataset_version_id": version_id,
                "customer_segments": total_segments,
                "customers": total_customers,
            }

    return result


if __name__ == "__main__":
    result = generate_customers()

    print("\nCUSTOMER GENERATION COMPLETED")

    for key, value in result.items():
        print(f"{key}: {value}")
