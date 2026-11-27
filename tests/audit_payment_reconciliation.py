
from sqlalchemy import select
from Bizpoint.database.base import Base
from Bizpoint.database.connection import SessionLocal
import Bizpoint.database.models


DATASET_VERSION_ID = "b580a1d713b1425685bbc624ef8473b6"

tables = Base.metadata.tables

sales_orders = tables["sales_orders"]
sales_payments = tables["sales_payments"]


def audit_payment_reconciliation():
    session = SessionLocal()

    try:
        orders = session.execute(
            select(
                sales_orders.c.id,
                sales_orders.c.order_number,
                sales_orders.c.total_amount_cents,
            ).where(
                sales_orders.c.dataset_version_id == DATASET_VERSION_ID
            )
        ).mappings().all()

        payments = session.execute(
            select(
                sales_payments.c.id,
                sales_payments.c.order_id,
                sales_payments.c.amount_cents,
                sales_payments.c.status,
            ).where(
                sales_payments.c.dataset_version_id == DATASET_VERSION_ID
            )
        ).mappings().all()

        order_map = {order["id"]: order for order in orders}

        invalid_links = 0
        invalid_amounts = 0
        invalid_statuses = 0
        duplicate_payments = 0
        successful_exceeds_order = 0

        payment_orders = set()
        successful_by_order = {}

        status_totals = {}

        for payment in payments:
            order_id = payment["order_id"]
            amount = payment["amount_cents"]
            status = payment["status"]

            status_totals[status] = status_totals.get(status, 0) + 1

            if order_id not in order_map:
                invalid_links += 1
                continue

            if amount <= 0:
                invalid_amounts += 1

            if status not in {
                "successful", "pending", "failed", "reversed"
            }:
                invalid_statuses += 1

            if order_id in payment_orders:
                duplicate_payments += 1

            payment_orders.add(order_id)

            if status == "successful":
                successful_by_order[order_id] = (
                    successful_by_order.get(order_id, 0) + amount
                )

        # Check successful collections against each order total.
        for order_id, collected in successful_by_order.items():
            if collected > order_map[order_id]["total_amount_cents"]:
                successful_exceeds_order += 1

        successful_payments = [
            payment for payment in payments
            if payment["status"] == "successful"
        ]

        pending_payments = [
            payment for payment in payments
            if payment["status"] == "pending"
        ]

        failed_payments = [
            payment for payment in payments
            if payment["status"] == "failed"
        ]

        reversed_payments = [
            payment for payment in payments
            if payment["status"] == "reversed"
        ]

        successful_total = sum(
            payment["amount_cents"]
            for payment in successful_payments
        )

        pending_total = sum(
            payment["amount_cents"]
            for payment in pending_payments
        )

        failed_total = sum(
            payment["amount_cents"]
            for payment in failed_payments
        )

        reversed_total = sum(
            payment["amount_cents"]
            for payment in reversed_payments
        )

        print("\nSALES PAYMENT RECONCILIATION")
        print("=" * 42)

        print(f"Sales orders: {len(orders)}")
        print(f"Payment records: {len(payments)}")

        print("\nPAYMENT STATUS BREAKDOWN")

        for status, count in sorted(status_totals.items()):
            print(f"{status}: {count}")

        print("\nPAYMENT AMOUNTS")
        print(f"Successful collections: ${successful_total / 100:,.2f}")
        print(f"Pending payments: ${pending_total / 100:,.2f}")
        print(f"Failed payments: ${failed_total / 100:,.2f}")
        print(f"Reversed payments: ${reversed_total / 100:,.2f}")

        print("\nDATA INTEGRITY")
        print(f"Invalid order links: {invalid_links}")
        print(f"Invalid payment amounts: {invalid_amounts}")
        print(f"Invalid statuses: {invalid_statuses}")
        print(f"Multiple payments per order: {duplicate_payments}")
        print(
            "Successful collections exceeding order totals: "
            f"{successful_exceeds_order}"
        )

        passed = all(
            value == 0
            for value in [
                invalid_links,
                invalid_amounts,
                invalid_statuses,
                duplicate_payments,
                successful_exceeds_order,
            ]
        )

        print("\nRESULT:", "PASSED" if passed else "REVIEW REQUIRED")

    finally:
        session.close()


if __name__ == "__main__":
    audit_payment_reconciliation()
