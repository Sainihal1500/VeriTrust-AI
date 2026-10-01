"""Detect account-data intents and extract requested record identifiers."""

import re

from agents.query_router import route_query

_ORDER_RE = re.compile(r"\bORD-\d{5}\b", re.IGNORECASE)
_CUSTOMER_RE = re.compile(r"\bCUST-\d{4}\b", re.IGNORECASE)
_CASE_RE = re.compile(r"\bCASE-\d{5}\b", re.IGNORECASE)


def extract_order_id(user_query: str):
    match = _ORDER_RE.search(user_query or "")
    return match.group(0).upper() if match else None


def extract_customer_id(user_query: str):
    match = _CUSTOMER_RE.search(user_query or "")
    return match.group(0).upper() if match else None


def extract_case_id(user_query: str):
    match = _CASE_RE.search(user_query or "")
    return match.group(0).upper() if match else None


def is_support_case_query(user_query: str) -> bool:
    query = (user_query or "").casefold()
    return bool(extract_case_id(user_query) or any(term in query for term in ("my support case", "my case", "case status", "my complaint status")))


def is_account_query(user_query: str) -> bool:
    query = (user_query or "").casefold()
    # General eligibility questions can be answered from public policy without
    # loading a customer's order or transaction record.
    policy_eligibility = re.search(r"\b(?:can|could|may)\s+i\b.{0,80}\b(?:cancel|return|refund)\b", query)
    if policy_eligibility and not any(term in query for term in ("status", "tracking", "where is", "when will", "has my", "did my")) and not extract_order_id(user_query):
        return False
    private_intents = (
        "my order", "my orders", "my package", "my parcel", "my shipment",
        "my delivery", "my purchase", "my account", "my profile",
        "my email", "my phone", "my address", "my name", "my membership",
        "my tier", "my contact details",
        "my support case", "my case", "case status", "my complaint status",
        "my email", "my phone", "my address", "my name", "my membership",
        "my tier", "my contact details",
        "my refund", "my payment", "my transaction", "my return",
        "where is my", "track my", "order status", "payment status",
        "refund status", "shipment status", "return status", "transaction history",
        "my tracking", "have i been charged", "was i charged",
    )
    return bool(extract_order_id(user_query) or extract_customer_id(user_query) or any(term in query for term in private_intents))


def route_account_query(user_query: str, query_category: str | None = None):
    order_id = extract_order_id(user_query)
    customer_id = extract_customer_id(user_query)
    case_id = extract_case_id(user_query)
    if order_id:
        route = "order_database"
    elif customer_id:
        route = "customer_database"
    elif case_id or is_support_case_query(user_query):
        route = "case_database"
    elif is_account_query(user_query):
        route = "account_database"
    else:
        category = query_category or route_query(user_query)
        route = {
            "product": "product_database",
            "warranty": "product_database",
            "promotion": "promotion_database",
        }.get(category, "knowledge_base")
    return {"route": route, "order_id": order_id, "customer_id": customer_id, "case_id": case_id}
