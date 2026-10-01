"""Deterministic, fictional customer and order records for VeriCommerce demos.

The first five customers and orders retain the original sample identifiers so
existing VeriTrust demos continue to work. All records after those fixtures are
generated locally from a fixed seed and contain synthetic contact details.
"""

from datetime import date, timedelta
import random

from database.catalog_data import PRODUCTS

AS_OF_DATE = date(2026, 9, 30)
_rng = random.Random(73421)
_first_names = ["Aarav", "Diya", "Ishaan", "Mira", "Kabir", "Anaya", "Rohan", "Tara", "Neel", "Aditi", "Reyansh", "Ira", "Arnav", "Kiara", "Dev", "Myra", "Vivaan", "Sara", "Kian", "Avni"]
_last_names = ["Mehta", "Nair", "Kapoor", "Iyer", "Desai", "Bose", "Rao", "Menon", "Shah", "Das", "Patel", "Kulkarni", "Sethi", "Pillai", "Ghosh", "Malhotra"]
_locations = [("Hyderabad", "Telangana"), ("Bengaluru", "Karnataka"), ("Chennai", "Tamil Nadu"), ("Pune", "Maharashtra"), ("Kochi", "Kerala"), ("Ahmedabad", "Gujarat"), ("Jaipur", "Rajasthan"), ("Kolkata", "West Bengal"), ("Indore", "Madhya Pradesh"), ("Lucknow", "Uttar Pradesh")]
_tiers = ["standard", "silver", "gold", "platinum"]
_methods = ["UPI", "Credit Card", "Debit Card", "Cash on Delivery", "Net Banking"]

_fixture_customers = {
    1001: ("Rahul Sharma", "Hyderabad", "Telangana", "gold"),
    1002: ("Priya Reddy", "Bengaluru", "Karnataka", "silver"),
    1003: ("Arjun Kumar", "Chennai", "Tamil Nadu", "platinum"),
    1004: ("Sneha Rao", "Pune", "Maharashtra", "silver"),
    1005: ("Vikram Singh", "Chennai", "Tamil Nadu", "gold"),
}

CUSTOMERS: dict[str, dict] = {}
for _number in range(1001, 1101):
    _customer_id = f"CUST-{_number}"
    if _number in _fixture_customers:
        _name, _city, _state, _tier = _fixture_customers[_number]
    else:
        _name = f"{_first_names[(_number * 7) % len(_first_names)]} {_last_names[(_number * 11) % len(_last_names)]}"
        _city, _state = _locations[(_number * 3) % len(_locations)]
        _tier = _tiers[(_number * 13) % len(_tiers)]
    _created = AS_OF_DATE - timedelta(days=90 + (_number * 37) % 1600)
    CUSTOMERS[_customer_id] = {
        "customer_id": _customer_id,
        "name": _name,
        "email": f"customer{_number}@demo.vericommerce.example",
        "phone": f"+91-90000{_number:05d}",
        "membership_tier": _tier,
        "loyalty_tier": _tier,
        "account_status": "active" if _number % 23 else "review",
        "created_at": _created.isoformat(),
        "default_city": _city,
        "default_state": _state,
        "preferred_language": ("English", "Hindi", "Tamil", "Telugu", "Kannada")[_number % 5],
    }


_fixture_orders = {
    10001: {"customer_id": "CUST-1001", "product_id": "PRD-20001", "product_name": "NovaBook Pro 14", "quantity": 1, "unit_price": 84999, "order_date": "2026-09-28", "order_status": "shipped", "payment_status": "successful", "payment_method": "UPI", "tracking_number": "TRK-IND-10001", "carrier": "VeriShip", "estimated_delivery": "2026-10-03"},
    10002: {"customer_id": "CUST-1002", "product_id": "PRD-20008", "product_name": "SoundMax Wireless Headphones", "quantity": 1, "unit_price": 6999, "order_date": "2026-09-29", "order_status": "processing", "payment_status": "successful", "payment_method": "Credit Card", "tracking_number": None, "carrier": None, "estimated_delivery": "2026-10-05"},
    10003: {"customer_id": "CUST-1003", "product_id": "PRD-20006", "product_name": "VisionTab X11", "quantity": 1, "unit_price": 32999, "order_date": "2026-09-25", "order_status": "delivered", "payment_status": "successful", "payment_method": "UPI", "tracking_number": "TRK-IND-10003", "carrier": "VeriShip", "estimated_delivery": "2026-09-28", "actual_delivery": "2026-09-28", "return_status": "approved", "refund_status": "completed"},
    10004: {"customer_id": "CUST-1004", "product_id": "PRD-20020", "product_name": "PowerCore 20000", "quantity": 2, "unit_price": 1999, "order_date": "2026-09-20", "order_status": "cancelled", "payment_status": "refund_pending", "payment_method": "Debit Card", "tracking_number": None, "carrier": None, "estimated_delivery": None, "cancellation_status": "cancelled", "refund_status": "processing", "return_status": "cancelled"},
    10005: {"customer_id": "CUST-1005", "product_id": "PRD-20010", "product_name": "SmartView 4K Monitor", "quantity": 1, "unit_price": 24999, "order_date": "2026-09-27", "order_status": "out_for_delivery", "payment_status": "successful", "payment_method": "Credit Card", "tracking_number": "TRK-IND-10005", "carrier": "VeriShip", "estimated_delivery": "2026-10-01"},
}

ORDERS: dict[str, dict] = {}
for _sequence in range(1, 321):
    _numeric_id = 10000 + _sequence
    _order_id = f"ORD-{_numeric_id}"
    if _numeric_id in _fixture_orders:
        _source = dict(_fixture_orders[_numeric_id])
    else:
        _customer_number = 1001 + ((_sequence * 37 + 13) % 100)
        _customer_id = f"CUST-{_customer_number}"
        _product = PRODUCTS[(_sequence * 17 + 5) % len(PRODUCTS)]
        _quantity = 1 + (_sequence % 3 == 0)
        _order_date_value = AS_OF_DATE - timedelta(days=(_sequence * 7) % 150)
        _status_selector = _sequence % 10
        _status = ["delivered", "shipped", "processing", "out_for_delivery", "delivered", "cancelled", "delivered", "delivered", "payment_failed", "shipped"][_status_selector]
        _refund_status = "processing" if _status == "cancelled" else (("completed" if _sequence % 2 == 0 else "processing") if _sequence % 3 == 0 else "not_requested")
        _has_return = _status != "cancelled" and (_sequence % 3 == 1 or _sequence % 10 == 0)
        _return_status = "cancelled" if _status == "cancelled" else (("approved" if _sequence % 2 == 0 else "requested") if _has_return else "not_requested")
        _location = CUSTOMERS[_customer_id]
        _tracking = None if _status in {"processing", "cancelled", "payment_failed"} else f"TRK-IND-{_numeric_id}"
        _source = {
            "customer_id": _customer_id,
            "product_id": _product["product_id"],
            "product_name": _product["name"],
            "quantity": int(_quantity),
            "unit_price": _product["price"],
            "order_date": _order_date_value.isoformat(),
            "order_status": _status,
            "payment_status": "failed" if _status == "payment_failed" else ("refund_pending" if _status == "cancelled" else "successful"),
            "payment_method": "Cash on Delivery" if _sequence % 17 == 0 and _status == "delivered" else [_method for _method in _methods if _method != "Cash on Delivery"][_sequence % 4],
            "tracking_number": _tracking,
            "carrier": "VeriShip" if _tracking else None,
            "estimated_delivery": (_order_date_value + timedelta(days=5 + _sequence % 3)).isoformat() if _status not in {"cancelled", "payment_failed"} else None,
            "refund_status": _refund_status,
            "return_status": _return_status,
            "cancellation_status": "cancelled" if _status == "cancelled" else "not_requested",
        }
        if _status == "delivered":
            _source["actual_delivery"] = (_order_date_value + timedelta(days=3 + _sequence % 5)).isoformat()
    _customer = CUSTOMERS[_source["customer_id"]]
    _product_data = next(product for product in PRODUCTS if product["product_id"] == _source["product_id"])
    _total = int(_source["unit_price"] * _source["quantity"])
    _city = _customer["default_city"]
    _state = _customer["default_state"]
    _status = _source["order_status"]
    _order = {
        "order_id": _order_id,
        "customer_id": _source["customer_id"],
        "product_id": _source["product_id"],
        "product_name": _source["product_name"],
        "product": _source["product_name"],
        "category": _product_data["category"],
        "quantity": int(_source["quantity"]),
        "unit_price": int(_source["unit_price"]),
        "total_amount": _total,
        "amount": _total,
        "currency": "INR",
        "order_date": _source["order_date"],
        "order_status": _status,
        "status": _status,
        "payment_status": _source["payment_status"],
        "payment_method": _source["payment_method"],
        "shipment_id": f"SHIP-{_numeric_id}",
        "tracking_number": _source.get("tracking_number"),
        "carrier": _source.get("carrier"),
        "estimated_delivery": _source.get("estimated_delivery"),
        "actual_delivery": _source.get("actual_delivery"),
        "shipping_address": f"{100 + _sequence % 800} Demo Avenue, {_city}, {_state}",
        "cancellation_status": _source.get("cancellation_status", "not_requested"),
        "return_status": _source.get("return_status", "not_requested"),
        "refund_status": _source.get("refund_status", "not_requested"),
    }
    ORDERS[_order_id] = _order


def get_customer(customer_id: str):
    return CUSTOMERS.get(customer_id)


def get_order(order_id: str):
    return ORDERS.get(order_id)


def get_customer_orders(customer_id: str):
    return [order for order in ORDERS.values() if order["customer_id"] == customer_id]


def get_order_for_customer(order_id: str, customer_id: str):
    order = ORDERS.get(order_id)
    return order if order and order["customer_id"] == customer_id else None


def search_orders(customer_id: str, status: str | None = None):
    orders = get_customer_orders(customer_id)
    if status:
        orders = [order for order in orders if order["order_status"].casefold() == status.casefold()]
    return orders


def customer_summary(customer_id: str):
    customer = get_customer(customer_id)
    if not customer:
        return None
    orders = get_customer_orders(customer_id)
    return {"customer": customer, "orders": orders, "order_count": len(orders), "total_spend": sum(order["total_amount"] for order in orders)}
