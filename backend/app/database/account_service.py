"""Authorization-enforcing account and catalog service functions."""

from database.catalog_data import PROMOTIONS, PRODUCTS, search_products
from database.customer_data import get_customer, get_customer_orders, get_order
from database.support_data import get_customer_support_cases, get_support_case
from database.transaction_service import get_customer_transaction_summary, get_order_transaction_summary
from security.access_control import verify_customer_access, verify_order_access


def get_order_information(order_id: str, session_id: str | None = None):
    """Return an order and its transactions only after ownership verification."""
    order = get_order(order_id)
    access = verify_order_access(session_id, order)
    if not access["allowed"]:
        # Do not reveal whether an order exists or who owns it.
        return {"found": False, "authorized": False, "type": "order", "message": "Order could not be found or accessed."}
    return {"found": True, "authorized": True, "type": "order", "data": order}


def get_customer_information(customer_id: str | None = None, session_id: str | None = None):
    access = verify_customer_access(session_id, customer_id)
    if not access["allowed"]:
        return {"found": False, "authorized": False, "type": "customer", "message": "Customer information could not be accessed."}
    customer = get_customer(access["customer_id"])
    if not customer:
        return {"found": False, "authorized": True, "type": "customer", "message": "Customer record was not found."}
    return {"found": True, "authorized": True, "type": "customer", "data": customer}


def get_customer_order_information(customer_id: str | None = None, session_id: str | None = None):
    access = verify_customer_access(session_id, customer_id)
    if not access["allowed"]:
        return {"found": False, "authorized": False, "type": "customer_orders", "message": "Order information could not be accessed."}
    orders = get_customer_orders(access["customer_id"])
    return {"found": bool(orders), "authorized": True, "type": "customer_orders", "data": orders}


def get_order_transaction_information(order_id: str, session_id: str | None = None):
    secured_order = get_order_information(order_id, session_id)
    if not secured_order["found"]:
        return {"found": False, "authorized": False, "type": "order_transactions", "message": "Transaction information could not be accessed."}
    summary = get_order_transaction_summary(order_id, session_id)
    if summary is None:
        return {"found": False, "authorized": False, "type": "order_transactions", "message": "Transaction information could not be accessed."}
    return {"found": True, "authorized": True, "type": "order_transactions", "data": summary}


def get_customer_transaction_information(customer_id: str | None = None, session_id: str | None = None):
    access = verify_customer_access(session_id, customer_id)
    if not access["allowed"]:
        return {"found": False, "authorized": False, "type": "customer_transactions", "message": "Transaction information could not be accessed."}
    summary = get_customer_transaction_summary(access["customer_id"], session_id)
    if summary is None:
        return {"found": False, "authorized": False, "type": "customer_transactions", "message": "Transaction information could not be accessed."}
    return {"found": True, "authorized": True, "type": "customer_transactions", "data": summary}


def get_product_information(query: str):
    products = search_products(query)
    return {"found": bool(products), "type": "products", "data": products}


def get_promotion_information():
    return {"found": bool(PROMOTIONS), "type": "promotions", "data": PROMOTIONS}


def get_support_case_information(case_id: str | None = None, session_id: str | None = None):
    """Return a support case only to its authenticated customer."""
    if case_id:
        case = get_support_case(case_id)
        access = verify_customer_access(session_id, case.get("customer_id") if case else None)
        if not case or not access["allowed"]:
            return {"found": False, "authorized": False, "type": "support_case", "message": "Support-case information could not be accessed."}
        return {"found": True, "authorized": True, "type": "support_case", "data": case}
    access = verify_customer_access(session_id)
    if not access["allowed"]:
        return {"found": False, "authorized": False, "type": "support_cases", "message": "Support-case information could not be accessed."}
    cases = get_customer_support_cases(access["customer_id"])
    return {"found": bool(cases), "authorized": True, "type": "support_cases", "data": cases}
