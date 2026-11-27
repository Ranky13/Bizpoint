
from sqlalchemy import select, func

from Bizpoint.database.connection import SessionLocal
from Bizpoint.database.models import (
    Dataset,
    DatasetVersion,
    ProductCategory,
    Brand,
    Product,
)

from Bizpoint.data_generation.config import DATASET_NAME
from Bizpoint.data_generation.utils import create_generators


def generate_products():
    """Generate product categories, brands and products."""

    random_generator, numpy_generator, fake = create_generators()

    category_data = [
        ("Electronics", "ELEC", "Electronic devices and accessories"),
        ("Clothing", "CLOTH", "Apparel and fashion products"),
        ("Home and Kitchen", "HOME", "Household and kitchen products"),
        ("Beauty and Personal Care", "BEAUTY", "Personal care and beauty products"),
        ("Food and Beverages", "FOOD", "Packaged food and beverage products"),
        ("Sports and Outdoors", "SPORT", "Sports and outdoor equipment"),
        ("Office Supplies", "OFFICE", "Office and stationery products"),
        ("Health and Wellness", "HEALTH", "Health and wellness products"),
    ]

    brand_data = [
        ("NovaTech", "NOVATECH"),
        ("UrbanStyle", "URBAN"),
        ("HomeEssentials", "HOMEESS"),
        ("PureGlow", "PUREGLOW"),
        ("FreshChoice", "FRESH"),
        ("ActiveLife", "ACTIVE"),
        ("OfficePro", "OFFICEPRO"),
        ("WellCare", "WELLCARE"),
        ("PrimeGoods", "PRIME"),
        ("EverydayPlus", "EVERYDAY"),
    ]

    product_types = {
        "ELEC": [
            "Wireless Headphones", "Bluetooth Speaker",
            "Smart Watch", "USB Charger", "Power Bank",
            "Laptop Stand", "Wireless Mouse", "Keyboard",
            "Phone Case", "LED Monitor", "Webcam",
            "Portable SSD", "Tablet Stand",
        ],
        "CLOTH": [
            "Cotton T-Shirt", "Denim Jeans", "Casual Shirt",
            "Sports Jacket", "Running Shorts", "Hoodie",
            "Summer Dress", "Formal Trousers", "Polo Shirt",
            "Winter Coat", "Sneakers", "Canvas Shoes",
            "Baseball Cap",
        ],
        "HOME": [
            "Electric Kettle", "Blender", "Dinner Plate Set",
            "Storage Container", "Table Lamp", "Bed Sheet Set",
            "Cooking Pot", "Water Bottle", "Wall Clock",
            "Food Processor", "Kitchen Knife Set", "Bath Towel",
            "Laundry Basket",
        ],
        "BEAUTY": [
            "Face Cleanser", "Body Lotion", "Hair Shampoo",
            "Conditioner", "Sunscreen", "Face Moisturizer",
            "Hair Oil", "Hand Cream", "Body Wash",
            "Facial Toner", "Lip Balm", "Hair Conditioner",
            "Skin Care Set",
        ],
        "FOOD": [
            "Breakfast Cereal", "Ground Coffee", "Green Tea",
            "Cooking Oil", "Pasta Pack", "Rice Pack",
            "Fruit Juice", "Oatmeal", "Peanut Butter",
            "Canned Beans", "Bottled Water", "Snack Pack",
            "Chocolate Bar",
        ],
        "SPORT": [
            "Yoga Mat", "Resistance Bands", "Football",
            "Basketball", "Skipping Rope", "Dumbbell Set",
            "Running Bottle", "Fitness Gloves", "Exercise Ball",
            "Sports Bag", "Cycling Helmet", "Tennis Racket",
            "Training Shoes",
        ],
        "OFFICE": [
            "Notebook Pack", "Ballpoint Pen Set", "Printer Paper",
            "Desk Organizer", "Stapler", "File Folder Set",
            "Whiteboard Marker", "Calculator", "Desk Pad",
            "Paper Clips", "Office Chair", "Printer Ink",
            "Document Tray",
        ],
        "HEALTH": [
            "Digital Thermometer", "First Aid Kit",
            "Reusable Ice Pack", "Pill Organizer",
            "Water Filter Bottle", "Heating Pad",
            "Digital Scale", "Eye Mask", "Hand Sanitizer",
            "Fitness Tracker", "Reusable Face Mask",
            "Massage Roller", "Support Pillow",
        ],
    }

    # Selling price ranges in cents, by category.
    price_ranges = {
        "ELEC": (1500, 250000),
        "CLOTH": (1000, 12000),
        "HOME": (800, 45000),
        "BEAUTY": (500, 15000),
        "FOOD": (200, 8000),
        "SPORT": (1000, 50000),
        "OFFICE": (200, 25000),
        "HEALTH": (500, 35000),
    }

    product_count = 100

    with SessionLocal() as session:
        with session.begin():

            # Retrieve dataset and version.
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

            # Create product categories.
            categories = {}

            for name, code, description in category_data:

                category = session.scalar(
                    select(ProductCategory).where(
                        ProductCategory.dataset_version_id == version_id,
                        ProductCategory.category_code == code,
                    )
                )

                if category is None:
                    category = ProductCategory(
                        dataset_version_id=version_id,
                        category_name=name,
                        category_code=code,
                        description=description,
                    )
                    session.add(category)
                    session.flush()

                categories[code] = category

            print("PRODUCT CATEGORIES:", len(categories))

            # Create brands.
            brands = {}

            for name, code in brand_data:

                brand = session.scalar(
                    select(Brand).where(
                        Brand.dataset_version_id == version_id,
                        Brand.brand_code == code,
                    )
                )

                if brand is None:
                    brand = Brand(
                        dataset_version_id=version_id,
                        brand_name=name,
                        brand_code=code,
                        description=f"Synthetic product brand: {name}",
                    )
                    session.add(brand)
                    session.flush()

                brands[code] = brand

            print("BRANDS:", len(brands))

            # Generate products.
            category_codes = list(categories.keys())
            brand_codes = list(brands.keys())

            for number in range(1, product_count + 1):

                sku = f"PRD{number:05d}"

                existing_product = session.scalar(
                    select(Product).where(
                        Product.dataset_version_id == version_id,
                        Product.sku == sku,
                    )
                )

                if existing_product is not None:
                    continue

                category_code = random_generator.choice(category_codes)

                product_name = (
                    random_generator.choice(
                        product_types[category_code]
                    )
                    + f" Model {number:03d}"
                )

                brand = random_generator.choice(brand_codes)

                minimum_price, maximum_price = price_ranges[
                    category_code
                ]

                unit_price_cents = random_generator.randint(
                    minimum_price,
                    maximum_price,
                )

                # Product cost is between 45% and 80% of selling price.
                cost_percentage = random_generator.uniform(0.45, 0.80)

                unit_cost_cents = int(
                    unit_price_cents * cost_percentage
                )

                product_status = random_generator.choices(
                    ["active", "inactive", "discontinued"],
                    weights=[90, 7, 3],
                    k=1,
                )[0]

                product = Product(
                    dataset_version_id=version_id,
                    sku=sku,
                    product_name=product_name,
                    description=(
                        f"{product_name} from the "
                        f"{categories[category_code].category_name} category."
                    ),
                    category_id=categories[category_code].id,
                    brand_id=brands[brand].id,
                    unit_price_cents=unit_price_cents,
                    unit_cost_cents=unit_cost_cents,
                    product_status=product_status,
                    is_active=(product_status == "active"),
                )

                session.add(product)

            session.flush()

            # Retrieve actual database counts.
            total_categories = session.scalar(
                select(func.count()).select_from(ProductCategory).where(
                    ProductCategory.dataset_version_id == version_id
                )
            )

            total_brands = session.scalar(
                select(func.count()).select_from(Brand).where(
                    Brand.dataset_version_id == version_id
                )
            )

            total_products = session.scalar(
                select(func.count()).select_from(Product).where(
                    Product.dataset_version_id == version_id
                )
            )

            result = {
                "dataset_version_id": version_id,
                "product_categories": total_categories,
                "brands": total_brands,
                "products": total_products,
            }

    return result


if __name__ == "__main__":
    result = generate_products()

    print("\nPRODUCT GENERATION COMPLETED")

    for key, value in result.items():
        print(f"{key}: {value}")
