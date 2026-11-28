from datetime import date
from typing import Any

from Bizpoint.analytics.sales.products import get_product_performance


def _aggregate_segment(
    products: list[dict[str, Any]],
    field: str,
) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}

    for product in products:
        name = product[field]

        if name not in groups:
            groups[name] = {
                field: name,
                "product_count": 0,
                "products_with_sales": 0,
                "products_with_returns": 0,
                "product_order_combinations": 0,
                "units_sold": 0,
                "units_returned": 0,
                "gross_sales_cents": 0,
                "discount_amount_cents": 0,
                "net_sales_cents": 0,
                "returned_amount_cents": 0,
            }

        group = groups[name]

        group["product_count"] += 1
        group["products_with_sales"] += int(product["units_sold"] > 0)
        group["products_with_returns"] += int(
            product["units_returned"] > 0
        )
        group["product_order_combinations"] += product["order_count"]
        group["units_sold"] += product["units_sold"]
        group["units_returned"] += product["units_returned"]

        for amount_field in (
            "gross_sales_cents",
            "discount_amount_cents",
            "net_sales_cents",
            "returned_amount_cents",
        ):
            group[amount_field] += product[amount_field]

    results = list(groups.values())

    for row in results:
        for amount_field in (
            "gross_sales_cents",
            "discount_amount_cents",
            "net_sales_cents",
            "returned_amount_cents",
        ):
            row[f"{amount_field}_dollars"] = round(
                row[amount_field] / 100,
                2,
            )

        row["period_return_to_sales_percentage"] = (
            round(
                row["units_returned"] / row["units_sold"] * 100,
                2,
            )
            if row["units_sold"] > 0
            else None
        )

    return sorted(
        results,
        key=lambda row: row["net_sales_cents"],
        reverse=True,
    )


def get_sales_segments(
    dataset_version_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """
    Aggregate product sales and returns by category and brand.

    Uses the product performance service as the source of truth.
    """

    if not dataset_version_id:
        raise ValueError("dataset_version_id is required.")

    if start_date and end_date and start_date > end_date:
        raise ValueError("start_date cannot be later than end_date.")

    product_result = get_product_performance(
        dataset_version_id=dataset_version_id,
        start_date=start_date,
        end_date=end_date,
    )

    products = product_result["products"]

    categories = _aggregate_segment(
        products,
        "category_name",
    )

    brands = _aggregate_segment(
        products,
        "brand_name",
    )

    return {
        "dataset_version_id": dataset_version_id,
        "currency": "USD",
        "period": {
            "start_date": start_date,
            "end_date": end_date,
        },
        "categories": categories,
        "brands": brands,
    }
