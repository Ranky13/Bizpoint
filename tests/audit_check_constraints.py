
from Bizpoint.database.base import Base
import Bizpoint.database.models


metadata = Base.metadata

total_checks = 0

print("CHECK CONSTRAINT AUDIT")
print("=" * 60)

for table in sorted(metadata.tables.values(), key=lambda t: t.name):

    checks = [
        constraint
        for constraint in table.constraints
        if constraint.__class__.__name__ == "CheckConstraint"
    ]

    if checks:
        print(f"\nTABLE: {table.name}")

        for check in checks:
            total_checks += 1

            print(f"  NAME: {check.name}")
            print(f"  RULE: {check.sqltext}")

print("\n" + "=" * 60)
print("TOTAL CHECK CONSTRAINTS:", total_checks)
print("TABLES REGISTERED:", len(metadata.tables))
