"""Authorization helpers. Call these before loading account or transaction data."""

from security.session import get_session_customer, is_authenticated


def verify_customer_access(session_id: str | None, requested_customer_id: str | None = None):
    if not is_authenticated(session_id):
        return {"allowed": False, "reason": "An authenticated session is required."}
    session_customer = get_session_customer(session_id)
    if not session_customer:
        return {"allowed": False, "reason": "No customer is associated with this session."}
    if requested_customer_id and requested_customer_id.upper() != session_customer:
        return {"allowed": False, "reason": "The requested customer does not match the authenticated session."}
    return {"allowed": True, "reason": "Customer access verified.", "customer_id": session_customer}


def verify_order_access(session_id: str | None, order: dict | None):
    if not is_authenticated(session_id):
        return {"allowed": False, "reason": "An authenticated session is required."}
    session_customer = get_session_customer(session_id)
    if not session_customer:
        return {"allowed": False, "reason": "No customer is associated with this session."}
    if not order:
        return {"allowed": False, "reason": "Order access could not be verified."}
    if order.get("customer_id") != session_customer:
        return {"allowed": False, "reason": "The order does not belong to the authenticated session."}
    return {"allowed": True, "reason": "Order access verified.", "customer_id": session_customer}
