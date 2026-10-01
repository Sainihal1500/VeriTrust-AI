"""Deterministic synthetic product and promotion catalog for VeriCommerce."""

PRODUCTS = [
    {"product_id": "PRD-20001", "name": "NovaBook Pro 14", "category": "laptops", "brand": "Nova", "price": 84999, "stock": 24, "warranty_period": "2 years", "description": "14-inch productivity laptop with a high-resolution display.", "specifications": {"display": "14-inch 2.8K IPS", "memory": "16 GB", "storage": "512 GB SSD", "ports": ["USB-C", "USB-A", "HDMI"]}, "compatibility": "USB-C docks, HDMI displays, Bluetooth peripherals"},
    {"product_id": "PRD-20002", "name": "NovaBook Air 13", "category": "laptops", "brand": "Nova", "price": 64999, "stock": 31, "warranty_period": "1 year", "description": "Lightweight 13-inch laptop for study and everyday work.", "specifications": {"display": "13.3-inch FHD", "memory": "8 GB", "storage": "512 GB SSD", "ports": ["USB-C", "USB-A"]}, "compatibility": "USB-C displays and Bluetooth peripherals"},
    {"product_id": "PRD-20003", "name": "NovaBook Studio 16", "category": "laptops", "brand": "Nova", "price": 124999, "stock": 12, "warranty_period": "2 years", "description": "16-inch creator laptop with discrete graphics.", "specifications": {"display": "16-inch QHD", "memory": "32 GB", "storage": "1 TB SSD", "ports": ["USB-C", "HDMI", "SD card"]}, "compatibility": "USB-C docks, HDMI displays, SDXC cards"},
    {"product_id": "PRD-20004", "name": "VeriPhone S24", "category": "phones", "brand": "Veri", "price": 54999, "stock": 48, "warranty_period": "1 year", "description": "5G smartphone with an OLED display and dual cameras.", "specifications": {"display": "6.2-inch OLED", "memory": "8 GB", "storage": "256 GB", "network": "5G"}, "compatibility": "USB-C charging, Bluetooth 5.3, nano-SIM and eSIM"},
    {"product_id": "PRD-20005", "name": "VeriPhone Lite", "category": "phones", "brand": "Veri", "price": 24999, "stock": 63, "warranty_period": "1 year", "description": "Everyday 5G smartphone with a long-lasting battery.", "specifications": {"display": "6.5-inch FHD+", "memory": "6 GB", "storage": "128 GB", "network": "5G"}, "compatibility": "USB-C charging, Bluetooth 5.2, nano-SIM"},
    {"product_id": "PRD-20006", "name": "VisionTab X11", "category": "tablets", "brand": "Vision", "price": 32999, "stock": 27, "warranty_period": "1 year", "description": "11-inch tablet for streaming, reading, and productivity.", "specifications": {"display": "11-inch 2K", "memory": "8 GB", "storage": "128 GB", "ports": ["USB-C"]}, "compatibility": "Bluetooth keyboards, USB-C audio and charging"},
    {"product_id": "PRD-20007", "name": "VisionTab Mini 8", "category": "tablets", "brand": "Vision", "price": 17999, "stock": 39, "warranty_period": "1 year", "description": "Compact 8-inch tablet for travel and reading.", "specifications": {"display": "8-inch HD", "memory": "4 GB", "storage": "64 GB"}, "compatibility": "Bluetooth audio and USB-C charging"},
    {"product_id": "PRD-20008", "name": "SoundMax Wireless Headphones", "category": "headphones", "brand": "SoundMax", "price": 6999, "stock": 55, "warranty_period": "1 year", "description": "Over-ear wireless headphones with active noise reduction.", "specifications": {"battery": "Up to 35 hours", "connectivity": ["Bluetooth 5.3", "3.5 mm audio"]}, "compatibility": "Bluetooth phones, tablets, and computers; 3.5 mm audio devices"},
    {"product_id": "PRD-20009", "name": "SoundMax Buds Pro", "category": "headphones", "brand": "SoundMax", "price": 4999, "stock": 82, "warranty_period": "1 year", "description": "True wireless earbuds with a charging case.", "specifications": {"battery": "Up to 7 hours per charge", "connectivity": "Bluetooth 5.3", "water_resistance": "IPX4"}, "compatibility": "Bluetooth audio devices"},
    {"product_id": "PRD-20010", "name": "SmartView 4K Monitor", "category": "monitors", "brand": "SmartView", "price": 24999, "stock": 19, "warranty_period": "3 years", "description": "27-inch 4K monitor for work and media.", "specifications": {"display": "27-inch 4K IPS", "refresh_rate": "60 Hz", "ports": ["HDMI 2.1", "DisplayPort 1.4", "USB-C"]}, "compatibility": "HDMI, DisplayPort, or USB-C video output"},
    {"product_id": "PRD-20011", "name": "SmartView UltraWide 34", "category": "monitors", "brand": "SmartView", "price": 38999, "stock": 14, "warranty_period": "3 years", "description": "34-inch ultrawide monitor for multitasking.", "specifications": {"display": "34-inch WQHD", "refresh_rate": "100 Hz", "ports": ["HDMI", "DisplayPort", "USB-C"]}, "compatibility": "HDMI, DisplayPort, or USB-C video output"},
    {"product_id": "PRD-20012", "name": "KeyForm Mechanical Keyboard", "category": "keyboards", "brand": "KeyForm", "price": 5499, "stock": 42, "warranty_period": "2 years", "description": "Compact mechanical keyboard with replaceable keycaps.", "specifications": {"layout": "75%", "connection": ["USB-C", "Bluetooth"], "switches": "Tactile"}, "compatibility": "Windows, macOS, Linux, and Bluetooth-enabled devices"},
    {"product_id": "PRD-20013", "name": "KeyForm Office Keyboard", "category": "keyboards", "brand": "KeyForm", "price": 1999, "stock": 76, "warranty_period": "1 year", "description": "Full-size low-profile office keyboard.", "specifications": {"layout": "Full size", "connection": "USB-A", "switches": "Membrane"}, "compatibility": "Devices with a USB-A port"},
    {"product_id": "PRD-20014", "name": "Glide Pro Wireless Mouse", "category": "mice", "brand": "Glide", "price": 2499, "stock": 91, "warranty_period": "1 year", "description": "Wireless precision mouse with adjustable sensitivity.", "specifications": {"sensor": "Up to 2400 DPI", "connection": ["Bluetooth", "2.4 GHz USB receiver"]}, "compatibility": "Windows, macOS, and ChromeOS"},
    {"product_id": "PRD-20015", "name": "VeriFit Watch 3", "category": "smartwatches", "brand": "Veri", "price": 12999, "stock": 34, "warranty_period": "1 year", "description": "Smartwatch with activity tracking and notifications.", "specifications": {"display": "1.8-inch AMOLED", "battery": "Up to 8 days", "water_resistance": "5 ATM"}, "compatibility": "Android 10+ and iOS 16+ companion app"},
    {"product_id": "PRD-20016", "name": "CaptureOne Mirrorless M50", "category": "cameras", "brand": "CaptureOne", "price": 72999, "stock": 9, "warranty_period": "2 years", "description": "Mirrorless camera body with interchangeable lens mount.", "specifications": {"sensor": "24 MP APS-C", "video": "4K", "storage": "SDXC"}, "compatibility": "CaptureOne M-mount lenses and SDXC memory cards"},
    {"product_id": "PRD-20017", "name": "ViewPoint 55 4K TV", "category": "tvs", "brand": "ViewPoint", "price": 49999, "stock": 16, "warranty_period": "2 years", "description": "55-inch 4K smart television with streaming apps.", "specifications": {"display": "55-inch 4K LED", "refresh_rate": "60 Hz", "ports": ["3x HDMI", "USB"]}, "compatibility": "HDMI devices, Wi-Fi 5, and Bluetooth audio"},
    {"product_id": "PRD-20018", "name": "ConnectHub Wi-Fi 6 Router", "category": "routers", "brand": "ConnectHub", "price": 8999, "stock": 29, "warranty_period": "2 years", "description": "Dual-band Wi-Fi 6 router for home networks.", "specifications": {"wireless": "Wi-Fi 6 AX3000", "ports": ["1x WAN", "4x Gigabit LAN"]}, "compatibility": "IPv4/IPv6 broadband modems and Wi-Fi 5/6 clients"},
    {"product_id": "PRD-20019", "name": "StoreFast Portable SSD 1TB", "category": "storage devices", "brand": "StoreFast", "price": 7999, "stock": 44, "warranty_period": "3 years", "description": "Portable solid-state drive for backups and media.", "specifications": {"capacity": "1 TB", "interface": "USB 3.2 Gen 2", "connector": "USB-C"}, "compatibility": "USB-C or USB-A hosts with the included cable"},
    {"product_id": "PRD-20020", "name": "PowerCore 20000", "category": "power banks", "brand": "PowerCore", "price": 1999, "stock": 120, "warranty_period": "1 year", "description": "20,000 mAh portable battery with USB-C charging.", "specifications": {"capacity": "20,000 mAh", "ports": ["USB-C", "2x USB-A"], "output": "Up to 22.5 W"}, "compatibility": "USB-C and USB-A chargeable devices"},
    {"product_id": "PRD-20021", "name": "ClearCall USB Webcam", "category": "accessories", "brand": "ClearCall", "price": 3499, "stock": 37, "warranty_period": "1 year", "description": "1080p USB webcam with privacy shutter.", "specifications": {"video": "1080p at 30 fps", "connection": "USB-A"}, "compatibility": "Windows, macOS, and Linux video-call applications"},
    {"product_id": "PRD-20022", "name": "DeskDock USB-C 8-in-1", "category": "accessories", "brand": "DeskDock", "price": 4999, "stock": 26, "warranty_period": "2 years", "description": "USB-C dock for displays and desk peripherals.", "specifications": {"ports": ["HDMI", "USB-C PD", "3x USB-A", "Ethernet", "SD", "microSD"]}, "compatibility": "USB-C laptops supporting DisplayPort Alt Mode"},
    {"product_id": "PRD-20023", "name": "PowerCore GaN 65W Charger", "category": "accessories", "brand": "PowerCore", "price": 2999, "stock": 68, "warranty_period": "1 year", "description": "Compact 65 W USB-C wall charger.", "specifications": {"output": "65 W", "ports": ["2x USB-C", "1x USB-A"]}, "compatibility": "USB-C Power Delivery and USB-A chargeable devices"},
    {"product_id": "PRD-20024", "name": "SoundMax Desktop Speakers", "category": "accessories", "brand": "SoundMax", "price": 3999, "stock": 23, "warranty_period": "1 year", "description": "Compact powered stereo speakers for desks.", "specifications": {"connection": ["USB", "3.5 mm audio"], "power": "USB powered"}, "compatibility": "Computers and audio sources with USB power and 3.5 mm output"},
]

PRODUCTS_BY_ID = {item["product_id"]: item for item in PRODUCTS}

PROMOTIONS = [
    {"promotion_id": f"PROMO-{i:03d}", "name": name, "discount": discount, "valid_from": "2026-08-01", "valid_until": "2026-12-31", "minimum_order": minimum, "eligible_categories": categories, "payment_methods": methods, "status": "active", "terms": terms}
    for i, (name, discount, minimum, categories, methods, terms) in enumerate([
        ("Welcome 5", "5% up to INR 1,000", 2500, ["all"], ["all"], "New accounts; one redemption per customer."),
        ("Laptop Week", "INR 3,000", 50000, ["laptops"], ["all"], "Eligible NovaBook laptops only; while stocks last."),
        ("Audio Days", "10% up to INR 800", 4000, ["headphones", "accessories"], ["all"], "Eligible SoundMax audio products only."),
        ("UPI Checkout", "INR 500", 10000, ["all"], ["UPI"], "Payment must complete successfully through UPI."),
        ("Member Bonus", "7% up to INR 1,500", 15000, ["all"], ["all"], "Gold and platinum members; exclusions apply."),
        ("Monitor Upgrade", "INR 1,500", 20000, ["monitors"], ["all"], "One eligible SmartView monitor per order."),
        ("Tablet Bundle", "5%", 15000, ["tablets", "accessories"], ["all"], "Discount applies to eligible tablet and accessory bundles."),
        ("Camera Kit", "INR 2,000", 60000, ["cameras"], ["all"], "CaptureOne camera products only."),
        ("Weekend Delivery", "Free standard shipping", 5000, ["all"], ["all"], "Shipping benefit does not change delivery estimates."),
        ("Power Essentials", "8% up to INR 400", 1500, ["power banks", "accessories"], ["all"], "Eligible PowerCore items only."),
        ("Smart Home", "INR 750", 8000, ["routers"], ["all"], "One ConnectHub router per customer."),
        ("Storage Sale", "6% up to INR 600", 5000, ["storage devices"], ["all"], "Eligible StoreFast drives only."),
    ], start=1)]


def search_products(query: str) -> list[dict]:
    """Return products with names or identifiers mentioned in a query."""
    normalized = query.casefold()
    matches = [
        product for product in PRODUCTS
        if product["name"].casefold() in normalized
        or product["product_id"].casefold() in normalized
    ]
    if matches:
        return matches
    category_aliases = {
        "laptop": "laptops", "phone": "phones", "tablet": "tablets",
        "headphone": "headphones", "monitor": "monitors", "keyboard": "keyboards",
        "mouse": "mice", "watch": "smartwatches", "camera": "cameras",
        "television": "tvs", "tv": "tvs", "router": "routers",
        "ssd": "storage devices", "drive": "storage devices", "power bank": "power banks",
    }
    categories = {target for word, target in category_aliases.items() if word in normalized}
    return [product for product in PRODUCTS if product["category"] in categories][:6]
