"""Deterministic synthetic support-case data for dashboard and demo use."""

from datetime import date, timedelta

from database.customer_data import CUSTOMERS, ORDERS

_topics = ["Delivery delay", "Refund status", "Payment issue", "Product setup", "Return request", "Warranty question", "Account access"]
_statuses = ["open", "in_progress", "waiting_for_customer", "resolved"]
SUPPORT_CASES = {}
for _index in range(1, 181):
    _customer_number = 1001 + ((_index * 17) % len(CUSTOMERS))
    _customer_id = f"CUST-{_customer_number}"
    _customer_orders = [order for order in ORDERS.values() if order["customer_id"] == _customer_id]
    _order_id = _customer_orders[(_index * 11) % len(_customer_orders)]["order_id"]
    _created = date(2026, 9, 30) - timedelta(days=(_index * 7) % 120)
    SUPPORT_CASES[f"CASE-{_index:05d}"] = {
        "case_id": f"CASE-{_index:05d}",
        "customer_id": _customer_id,
        "order_id": _order_id,
        "topic": _topics[_index % len(_topics)],
        "status": _statuses[_index % len(_statuses)],
        "priority": ("high" if _index % 9 == 0 else "normal"),
        "created_at": _created.isoformat(),
        "updated_at": (_created + timedelta(days=min(_index % 4, 2))).isoformat(),
        "channel": ("chat", "email", "phone", "web")[(_index - 1) % 4],
    }


def get_support_case(case_id: str):
    return SUPPORT_CASES.get((case_id or "").upper())


def get_customer_support_cases(customer_id: str):
    return [case for case in SUPPORT_CASES.values() if case["customer_id"] == customer_id]
