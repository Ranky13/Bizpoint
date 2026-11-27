
from Bizpoint.database.base import Base
import Bizpoint.database.models


metadata = Base.metadata

errors = []
checked_relationships = 0


for table in metadata.tables.values():

    # Only inspect dataset-scoped child tables.
    if "dataset_version_id" not in table.columns:
        continue

    for constraint in table.foreign_key_constraints:

        elements = list(constraint.elements)

        if not elements:
            continue

        # Identify the referenced parent table.
        parent_table = elements[0].column.table

        # Only inspect relationships where both tables
        # are dataset-scoped.
        if "dataset_version_id" not in parent_table.columns:
            continue

        checked_relationships += 1

        # Build the child-to-parent column mapping.
        column_mapping = {
            element.parent.name: element.column.name
            for element in elements
        }

        # Confirm the relationship includes the dataset version.
        if column_mapping.get("dataset_version_id") != "dataset_version_id":

            errors.append(
                f"{table.name}: relationship to {parent_table.name} "
                "does not use a composite dataset-version foreign key."
            )


print("DATASET-SCOPED RELATIONSHIPS CHECKED:", checked_relationships)

print("\nDATASET ISOLATION AUDIT:")

if errors:
    print("FAILED: Dataset isolation issues detected.")

    for error in errors:
        print("-", error)

else:
    print("PASSED: No dataset isolation issues detected.")
    print(
        "All checked relationships between dataset-scoped "
        "tables use matching dataset-version foreign keys."
    )
