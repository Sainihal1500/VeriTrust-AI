"""Demo session registry; production deployments should use signed sessions."""

from database.customer_data import CUSTOMERS

SESSIONS = {
    f"SESSION-{int(customer_id[-4:])}": {
        "session_id": f"SESSION-{int(customer_id[-4:])}",
        "customer_id": customer_id,
        "authenticated": True,
    }
    for customer_id in CUSTOMERS
}


def get_session(session_id: str | None):
    if not session_id:
        return None
    return SESSIONS.get(session_id.strip().upper())


def is_authenticated(session_id: str | None) -> bool:
    session = get_session(session_id)
    return bool(session and session.get("authenticated"))


def get_session_customer(session_id: str | None):
    session = get_session(session_id)
    if not session or not session.get("authenticated"):
        return None
    return session.get("customer_id")
