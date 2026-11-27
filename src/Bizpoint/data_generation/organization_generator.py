
from sqlalchemy import select

from Bizpoint.database.connection import SessionLocal
from Bizpoint.database.models import (
    Dataset,
    DatasetVersion,
    Region,
    Store,
    Department,
    Employee,
)

from Bizpoint.data_generation.config import (
    DATASET_NAME,
    START_DATE,
    END_DATE,
)

from Bizpoint.data_generation.utils import create_generators


def generate_organization():
    """
    Generate regions, stores, departments and employees
    for the initial synthetic dataset.
    """

    random_generator, numpy_generator, fake = create_generators()

    with SessionLocal() as session:

        with session.begin():

            # Retrieve the initial dataset.
            dataset = session.scalar(
                select(Dataset).where(
                    Dataset.name == DATASET_NAME
                )
            )

            if dataset is None:
                raise ValueError("Dataset does not exist.")

            # Retrieve dataset version 1.
            version = session.scalar(
                select(DatasetVersion).where(
                    DatasetVersion.dataset_id == dataset.id,
                    DatasetVersion.version_number == 1,
                )
            )

            if version is None:
                raise ValueError("Dataset version 1 does not exist.")

            version_id = version.id

            # ------------------------------------------------
            # 1. GENERATE REGIONS
            # ------------------------------------------------

            region_data = [
                ("North America", "NA"),
                ("South America", "SA"),
                ("Europe", "EU"),
                ("Asia Pacific", "APAC"),
            ]

            regions = {}

            for name, code in region_data:

                region = session.scalar(
                    select(Region).where(
                        Region.dataset_version_id == version_id,
                        Region.region_code == code,
                    )
                )

                if region is None:
                    region = Region(
                        dataset_version_id=version_id,
                        region_name=name,
                        region_code=code,
                        description=f"Business operating region: {name}",
                    )

                    session.add(region)
                    session.flush()

                regions[code] = region

            print("REGIONS:", len(regions))

            # ------------------------------------------------
            # 2. GENERATE STORES
            # ------------------------------------------------

            store_data = [
                ("New York Central", "NYC", "NA"),
                ("Los Angeles West", "LAW", "NA"),
                ("Toronto Downtown", "TOR", "NA"),
                ("Sao Paulo Central", "SAO", "SA"),
                ("London Central", "LON", "EU"),
                ("Berlin Mitte", "BER", "EU"),
                ("Singapore Central", "SGP", "APAC"),
                ("Sydney Central", "SYD", "APAC"),
            ]

            stores = {}

            for name, code, region_code in store_data:

                store = session.scalar(
                    select(Store).where(
                        Store.dataset_version_id == version_id,
                        Store.store_code == code,
                    )
                )

                if store is None:
                    store = Store(
                        dataset_version_id=version_id,
                        store_name=name,
                        store_code=code,
                        region_id=regions[region_code].id,
                        address=fake.address(),
                        is_active=True,
                    )

                    session.add(store)
                    session.flush()

                stores[code] = store

            print("STORES:", len(stores))

            # ------------------------------------------------
            # 3. GENERATE DEPARTMENTS
            # ------------------------------------------------

            department_data = [
                ("Sales", "SALES", "Sales and revenue generation"),
                ("Finance", "FIN", "Financial planning and control"),
                ("Operations", "OPS", "Daily business operations"),
                ("Marketing", "MKT", "Marketing and customer acquisition"),
                ("Human Resources", "HR", "People and workforce management"),
                ("Inventory", "INV", "Stock and inventory management"),
                ("Customer Service", "CS", "Customer support and retention"),
                ("Management", "MGT", "Executive and strategic management"),
            ]

            departments = {}

            for name, code, description in department_data:

                department = session.scalar(
                    select(Department).where(
                        Department.dataset_version_id == version_id,
                        Department.department_code == code,
                    )
                )

                if department is None:
                    department = Department(
                        dataset_version_id=version_id,
                        department_name=name,
                        department_code=code,
                        description=description,
                    )

                    session.add(department)
                    session.flush()

                departments[code] = department

            print("DEPARTMENTS:", len(departments))

            # ------------------------------------------------
            # 4. GENERATE EMPLOYEES
            # ------------------------------------------------

            job_titles = {
                "SALES": ["Sales Associate", "Sales Representative", "Sales Manager"],
                "FIN": ["Accountant", "Financial Analyst", "Finance Manager"],
                "OPS": ["Operations Officer", "Operations Manager"],
                "MKT": ["Marketing Executive", "Marketing Manager"],
                "HR": ["HR Officer", "HR Manager"],
                "INV": ["Inventory Officer", "Inventory Manager"],
                "CS": ["Customer Support Officer", "Customer Service Manager"],
                "MGT": ["Business Manager", "General Manager"],
            }

            employee_count = 40

            department_codes = list(departments.keys())

            for number in range(1, employee_count + 1):

                employee_code = f"EMP{number:04d}"

                existing_employee = session.scalar(
                    select(Employee).where(
                        Employee.dataset_version_id == version_id,
                        Employee.employee_code == employee_code,
                    )
                )

                if existing_employee is not None:
                    continue

                department_code = random_generator.choice(
                    department_codes
                )

                first_name = fake.first_name()
                last_name = fake.last_name()

                employee = Employee(
                    dataset_version_id=version_id,
                    employee_code=employee_code,
                    first_name=first_name,
                    last_name=last_name,
                    department_id=departments[department_code].id,
                    job_title=random_generator.choice(
                        job_titles[department_code]
                    ),
                    email=(
                        f"{first_name.lower()}.{last_name.lower()}."
                        f"{number}@bizpoint.example"
                    ),
                    hire_date=fake.date_between_dates(
                        date_start=START_DATE,
                        date_end=END_DATE,
                    ),
                    employment_status=random_generator.choices(
                        ["active", "inactive", "on_leave", "terminated"],
                        weights=[85, 5, 7, 3],
                        k=1,
                    )[0],
                )

                session.add(employee)

            session.flush()

            print("EMPLOYEES: 40")

            result = {
                "dataset_id": dataset.id,
                "dataset_version_id": version_id,
                "regions": len(regions),
                "stores": len(stores),
                "departments": len(departments),
                "employees": session.scalar(
                    select(Employee.id).where(
                        Employee.dataset_version_id == version_id
                    ).limit(1)
                ) is not None,
            }

        return result


if __name__ == "__main__":

    result = generate_organization()

    print("\nORGANIZATION GENERATION COMPLETED")

    for key, value in result.items():
        print(f"{key}: {value}")
