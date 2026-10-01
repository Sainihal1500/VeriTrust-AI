"""Authorization-enforcing transaction service."""

from database.customer_data import get_order
from database.transaction_data import get_customer_transactions, get_payment_by_order, get_refund_by_order, get_return_by_order, get_shipment_by_order
from security.access_control import verify_customer_access, verify_order_access


def get_order_transaction_summary(order_id: str, session_id: str | None = None):
    """Return payment, refund, shipment, and return data only for the owner."""
    access = verify_order_access(session_id, get_order(order_id))
    if not access["allowed"]:
        return None
    return {
        "payment": get_payment_by_order(order_id),
        "refund": get_refund_by_order(order_id),
        "shipment": get_shipment_by_order(order_id),
        "return": get_return_by_order(order_id),
    }


def get_customer_transaction_summary(customer_id: str | None = None, session_id: str | None = None):
    """Return customer transaction history only for the authenticated owner."""
    access = verify_customer_access(session_id, customer_id)
    if not access["allowed"]:
        return None
    return get_customer_transactions(access["customer_id"])
