"""Deterministic synthetic payment, refund, shipment, and return records."""

from datetime import date, datetime, timedelta

from database.customer_data import AS_OF_DATE, CUSTOMERS, ORDERS

PAYMENTS: dict[str, dict] = {}
REFUNDS: dict[str, dict] = {}
SHIPMENTS: dict[str, dict] = {}
RETURNS: dict[str, dict] = {}

_carriers = ["VeriShip", "BlueDart", "Delhivery", "Ecom Express"]
_payment_statuses = {"successful": "captured", "failed": "failed", "refund_pending": "captured"}

for _sequence, (_order_id, _order) in enumerate(ORDERS.items(), start=1):
    _order_number = int(_order_id[-5:])
    _created = datetime.fromisoformat(f"{_order['order_date']}T10:{_sequence % 60:02d}:00")
    _payment_id = f"PAY-{_order_number}"
    _payment_status = _payment_statuses.get(_order["payment_status"], "captured")
    PAYMENTS[_payment_id] = {
        "payment_id": _payment_id,
        "order_id": _order_id,
        "customer_id": _order["customer_id"],
        "amount": _order["total_amount"],
        "currency": "INR",
        "payment_method": _order["payment_method"],
        "method": _order["payment_method"],
        "status": _payment_status,
        "transaction_reference": f"VC-PAY-{_order_number}",
        "created_at": _created.isoformat(timespec="minutes"),
        "transaction_date": _order["order_date"],
    }

    _tracking = _order.get("tracking_number")
    _shipment_status = {
        "delivered": "delivered", "shipped": "in_transit",
        "out_for_delivery": "out_for_delivery", "processing": "label_created",
        "cancelled": "cancelled", "payment_failed": "not_shipped",
        "return_requested": "delivered",
    }.get(_order["order_status"], "in_transit")
    _destination = CUSTOMERS[_order["customer_id"]]["default_city"]
    _estimated = _order.get("estimated_delivery")
    SHIPMENTS[f"SHIP-{_order_number}"] = {
        "shipment_id": f"SHIP-{_order_number}",
        "order_id": _order_id,
        "customer_id": _order["customer_id"],
        "carrier": _order.get("carrier") or _carriers[_sequence % len(_carriers)],
        "tracking_number": _tracking,
        "origin": "VeriCommerce Fulfillment Center, Hyderabad",
        "destination": _destination,
        "status": _shipment_status,
        "estimated_delivery": _estimated,
        "last_update": datetime.combine(AS_OF_DATE, datetime.min.time()).replace(hour=9, minute=_sequence % 60).isoformat(timespec="minutes"),
    }

    # The original five demo orders and a stable sample of generated orders
    # exercise refund status and amount lookups without inconsistent foreign keys.
    if _order_id == "ORD-10004":
        _refund_number = 10001
        _refund_status = "processing"
        _requested = "2026-09-21"
        _estimated_completion = "2026-10-03"
    elif _order_id == "ORD-10003":
        _refund_number = 10002
        _refund_status = "completed"
        _requested = "2026-09-28"
        _estimated_completion = "2026-09-30"
    elif _sequence > 5 and (_sequence % 3 == 0 or _order["order_status"] == "cancelled"):
        _refund_number = 10000 + _sequence
        _refund_status = "completed" if _sequence % 2 == 0 else "processing"
        _requested = (date.fromisoformat(_order["order_date"]) + timedelta(days=2)).isoformat()
        _estimated_completion = (date.fromisoformat(_requested) + timedelta(days=7)).isoformat()
    else:
        _refund_number = None

    if _refund_number is not None:
        REFUNDS[f"REF-{_refund_number}"] = {
            "refund_id": f"REF-{_refund_number}",
            "order_id": _order_id,
            "customer_id": _order["customer_id"],
            "amount": _order["total_amount"],
            "currency": "INR",
            "status": _refund_status,
            "reason": "Order cancellation" if _order["order_status"] == "cancelled" else "Customer return request",
            "refund_method": "original_payment_method",
            "requested_at": _requested,
            "requested_date": _requested,
            "processed_at": _requested if _refund_status == "completed" else None,
            "estimated_completion": _estimated_completion,
        }

    if _order_id == "ORD-10003":
        _return_number, _return_status, _reason = 10001, "approved", "Product damaged"
        _requested_at, _pickup = "2026-09-28", "2026-10-01"
    elif _order_id == "ORD-10004":
        _return_number, _return_status, _reason = 10002, "cancelled", "Cancellation before shipment"
        _requested_at, _pickup = "2026-09-21", None
    elif _sequence > 5 and _order["order_status"] != "cancelled" and (_sequence % 3 == 1 or _sequence % 10 == 0):
        _return_number = 10000 + _sequence
        _return_status = _order["return_status"]
        _reason = ("Damaged on arrival", "Wrong item received", "Changed mind")[_sequence % 3]
        _requested_at = (date.fromisoformat(_order["order_date"]) + timedelta(days=4)).isoformat()
        _pickup = (date.fromisoformat(_requested_at) + timedelta(days=2)).isoformat()
    else:
        _return_number = None

    if _return_number is not None:
        RETURNS[f"RET-{_return_number}"] = {
            "return_id": f"RET-{_return_number}",
            "order_id": _order_id,
            "customer_id": _order["customer_id"],
            "reason": _reason,
            "status": _return_status,
            "requested_at": _requested_at,
            "requested_date": _requested_at,
            "pickup_date": _pickup,
            "pickup_status": "cancelled" if _return_status == "cancelled" else ("scheduled" if _return_status == "approved" else ("completed" if _return_status == "completed" else "pending_approval")),
            "inspection_status": "not_started" if _return_status == "cancelled" else ("pending" if _return_status != "completed" else "passed"),
            "refund_eligibility": "not_applicable" if _return_status == "cancelled" else ("pending_inspection" if _return_status == "approved" else ("eligible" if _return_status == "completed" else "under_review")),
        }


def get_payment_by_order(order_id: str):
    return next((payment for payment in PAYMENTS.values() if payment["order_id"] == order_id), None)


def get_refund_by_order(order_id: str):
    return next((refund for refund in REFUNDS.values() if refund["order_id"] == order_id), None)


def get_shipment_by_order(order_id: str):
    return next((shipment for shipment in SHIPMENTS.values() if shipment["order_id"] == order_id), None)


def get_return_by_order(order_id: str):
    return next((return_record for return_record in RETURNS.values() if return_record["order_id"] == order_id), None)


def get_customer_transactions(customer_id: str):
    return {
        "payments": [item for item in PAYMENTS.values() if item["customer_id"] == customer_id],
        "refunds": [item for item in REFUNDS.values() if item["customer_id"] == customer_id],
        "shipments": [item for item in SHIPMENTS.values() if item["customer_id"] == customer_id],
        "returns": [item for item in RETURNS.values() if item["customer_id"] == customer_id],
    }
