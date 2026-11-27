from sqlalchemy import UniqueConstraint

from Bizpoint.database.base import Base
import Bizpoint.database.models

metadata = Base.metadata

errors = []
foreign_key_count = 0
composite_foreign_key_count = 0
dataset_scoped_count = 0


for table in metadata.tables.values():

    # Check all foreign-key constraints.
    for constraint in table.foreign_key_constraints:

        foreign_key_count += 1

        elements = list(constraint.elements)

        # Check composite foreign-key targets.
        if len(elements) > 1:

            composite_foreign_key_count += 1

            target_table = elements[0].column.table

            target_columns = {
                element.column.name
                for element in elements
            }

            # Confirm the referenced columns are unique.
            target_is_unique = any(
                isinstance(target_constraint, UniqueConstraint)
                and set(target_constraint.columns.keys()) == target_columns
                for target_constraint in target_table.constraints
            )

            if not target_is_unique:
                errors.append(
                    f"{table.name}: composite FK target "
                    f"{target_table.name} columns {target_columns} "
                    f"do not have a matching unique constraint."
                )

    # Check dataset-scoped tables.
    if "dataset_version_id" in table.columns:

        dataset_scoped_count += 1

        # Confirm the dataset version foreign key exists.
        has_version_fk = any(
            fk.target_fullname == "dataset_versions.id"
            for fk in table.c.dataset_version_id.foreign_keys
        )

        if not has_version_fk:
            errors.append(
                f"{table.name}: missing dataset_versions.id foreign key."
            )

        # Confirm the composite unique key exists.
        has_unique_version_id = any(
            isinstance(constraint, UniqueConstraint)
            and set(constraint.columns.keys())
            == {"dataset_version_id", "id"}
            for constraint in table.constraints
        )

        if not has_unique_version_id:
            errors.append(
                f"{table.name}: missing unique constraint "
                "(dataset_version_id, id)."
            )


print("FOREIGN KEY COUNT:", foreign_key_count)
print("COMPOSITE FOREIGN KEY COUNT:", composite_foreign_key_count)
print("DATASET-SCOPED TABLE COUNT:", dataset_scoped_count)

print("\nAUDIT RESULTS:")

if errors:
    print("FAILED: Issues detected.")

    for error in errors:
        print("-", error)

else:
    print("PASSED: No issues detected.")
    print("All checked foreign-key targets have matching unique constraints.")
    print("All dataset-scoped tables have the required version references.")
