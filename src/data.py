"""Small, inspectable datasets used by the teaching tools.

The point of this module is visibility. Learners can replace these structures
with a database or vector store without changing the graph topology.
"""

from __future__ import annotations

PRODUCT_CATALOG: list[dict] = [
    {
        "id": "PROD001",
        "name": "Air Jordan 1 Retro High OG",
        "category": "Footwear",
        "brand": "Nike",
        "price": 180,
        "rating": 4.8,
        "features": ["Leather upper", "Air-Sole cushioning", "Rubber outsole", "Iconic colorway"],
        "description": (
            "Classic basketball sneaker with premium leather construction and legendary style."
        ),
        "in_stock": True,
        "colors": ["Black/Red", "Chicago", "Royal Blue"],
    },
    {
        "id": "PROD002",
        "name": "Bose QuietComfort 45 Headphones",
        "category": "Electronics",
        "brand": "Bose",
        "price": 279,
        "rating": 4.7,
        "features": [
            "Active Noise Cancellation",
            "24-hour battery",
            "Bluetooth 5.1",
            "USB-C charging",
        ],
        "description": (
            "Premium wireless noise-cancelling headphones with legendary Bose sound quality."
        ),
        "in_stock": True,
        "colors": ["Black", "White Smoke"],
    },
    {
        "id": "PROD003",
        "name": "Sony WH-1000XM5 Headphones",
        "category": "Electronics",
        "brand": "Sony",
        "price": 399,
        "rating": 4.9,
        "features": [
            "Industry-leading ANC",
            "30-hour battery",
            "Speak-to-Chat",
            "LDAC Hi-Res Audio",
        ],
        "description": (
            "Sony's flagship noise-cancelling headphones with exceptional sound quality."
        ),
        "in_stock": True,
        "colors": ["Black", "Silver"],
    },
    {
        "id": "PROD004",
        "name": "Usha Maxx Air 400mm Table Fan",
        "category": "Home Appliances",
        "brand": "Usha",
        "price": 45,
        "rating": 4.3,
        "features": ["400mm sweep", "3-speed control", "Oscillation", "Low power consumption"],
        "description": "Powerful table fan with superior air delivery and energy efficiency.",
        "in_stock": True,
        "colors": ["White", "Blue"],
    },
    {
        "id": "PROD005",
        "name": "iPhone 15 Pro Max",
        "category": "Electronics",
        "brand": "Apple",
        "price": 1199,
        "rating": 4.8,
        "features": ["A17 Pro chip", "Titanium design", "48MP camera", "USB-C", "5x optical zoom"],
        "description": "Apple's most advanced iPhone with titanium design and professional camera.",
        "in_stock": True,
        "colors": ["Natural Titanium", "Blue Titanium", "Black Titanium"],
    },
    {
        "id": "PROD006",
        "name": "Samsung Galaxy S24 Ultra",
        "category": "Electronics",
        "brand": "Samsung",
        "price": 1299,
        "rating": 4.7,
        "features": ["Snapdragon 8 Gen 3", "200MP camera", "S Pen included", "Galaxy AI"],
        "description": (
            "Samsung's flagship smartphone with Galaxy AI and an exceptional camera system."
        ),
        "in_stock": True,
        "colors": ["Titanium Gray", "Titanium Black", "Titanium Violet"],
    },
    {
        "id": "PROD007",
        "name": "MacBook Air M3 13-inch",
        "category": "Electronics",
        "brand": "Apple",
        "price": 1099,
        "rating": 4.9,
        "features": ["M3 chip", "18-hour battery", "Liquid Retina display", "MagSafe charging"],
        "description": "Supercharged by M3 chip with all-day battery life and a stunning display.",
        "in_stock": True,
        "colors": ["Midnight", "Starlight", "Space Gray", "Silver"],
    },
    {
        "id": "PROD008",
        "name": "boAt Airdopes 141 TWS",
        "category": "Electronics",
        "brand": "boAt",
        "price": 29,
        "rating": 4.2,
        "features": ["42-hour playback", "ENx Technology", "IPX4 water resistance", "BEAST Mode"],
        "description": "True wireless earbuds with massive battery life and immersive sound.",
        "in_stock": True,
        "colors": ["Active Black", "Bold Blue", "Cherry Blossom"],
    },
]


ORDER_DATABASE: dict[str, dict] = {
    "ORD101": {
        "product": "Air Jordan 1 Retro High OG",
        "customer_name": "Rahul Sharma",
        "customer_email": "rahul.sharma@example.com",
        "status": "Shipped",
        "price": 180,
        "order_date": "2026-02-10",
        "estimated_delivery": "2026-02-13",
    },
    "ORD102": {
        "product": "Bose QuietComfort 45 Headphones",
        "customer_name": "Priya Patel",
        "customer_email": "priya.patel@example.com",
        "status": "Delayed",
        "delay_reason": "Bad weather conditions in transit region",
        "price": 279,
        "order_date": "2026-02-08",
        "estimated_delivery": "2026-02-15",
    },
    "ORD103": {
        "product": "Usha Maxx Air 400mm Table Fan",
        "customer_name": "Amit Kumar",
        "customer_email": "amit.kumar@example.com",
        "status": "Processing",
        "price": 45,
        "order_date": "2026-02-12",
        "estimated_delivery": "2026-02-20",
    },
    "ORD104": {
        "product": "iPhone 15 Pro Max",
        "customer_name": "Vikram Singh",
        "customer_email": "vikram.singh@example.com",
        "status": "Ordered",
        "price": 1199,
        "order_date": "2026-02-13",
        "estimated_delivery": "2026-02-17",
    },
}

ESCALATION_QUEUE: list[dict] = []


SUPPORT_POLICIES = """
SHIPPING OPTIONS:
- Rocket (Same-day): $19, available before 1 PM in participating cities
- Glide (3-4 days): $9, express delivery
- Cruise (7-8 days): Free on orders over $50

ESCALATION CRITERIA:
- Customer explicitly requests a human agent
- Complaint involves safety or legal issues
- Customer is highly frustrated or angry
- Issue cannot be resolved with available tools
""".strip()
