
from sqlalchemy import select

from Bizpoint.database.connection import SessionLocal
from Bizpoint.database.models import Dataset, DatasetVersion

from Bizpoint.data_generation.config import (
    DATASET_NAME,
    DATASET_DESCRIPTION,
)


def create_initial_dataset():
    """
    Create the initial synthetic dataset and its first draft version.

    Prevents duplicate creation if the generator is run again.
    """

    with SessionLocal() as session:

        with session.begin():

            # Check whether this dataset already exists.
            dataset = session.scalar(
                select(Dataset).where(
                    Dataset.name == DATASET_NAME
                )
            )

            if dataset is None:

                dataset = Dataset(
                    name=DATASET_NAME,
                    description=DATASET_DESCRIPTION,
                    source_type="synthetic",
                )

                session.add(dataset)
                session.flush()

                print("DATASET CREATED:", dataset.name)

            else:
                print("DATASET ALREADY EXISTS:", dataset.name)

            # Check whether version 1 already exists.
            version = session.scalar(
                select(DatasetVersion).where(
                    DatasetVersion.dataset_id == dataset.id,
                    DatasetVersion.version_number == 1,
                )
            )

            if version is None:

                version = DatasetVersion(
                    dataset_id=dataset.id,
                    version_number=1,
                    status="draft",
                )

                session.add(version)
                session.flush()

                print("DATASET VERSION CREATED:", version.version_number)

            else:
                print("DATASET VERSION ALREADY EXISTS:", version.version_number)

            result = {
                "dataset_id": dataset.id,
                "dataset_name": dataset.name,
                "dataset_version_id": version.id,
                "version_number": version.version_number,
                "version_status": version.status,
            }

        return result


if __name__ == "__main__":

    result = create_initial_dataset()

    print("\nINITIAL DATASET DETAILS")

    for key, value in result.items():
        print(f"{key}: {value}")
