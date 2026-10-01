"""Hybrid deterministic/LLM customer-service query router."""

import os
import re

from langchain_ollama import ChatOllama
from agents.llm_utils import ollama_available, strip_internal_reasoning

_MODEL = os.getenv("VERITRUST_CHAT_MODEL", "qwen3.5:latest")
_BASE_URL = os.getenv("OLLAMA_BASE_URL") or None
llm = ChatOllama(model=_MODEL, temperature=0, num_predict=24, base_url=_BASE_URL, client_kwargs={"timeout": 20})

_RULES = [
    ("privacy", ("privacy", "personal data", "delete my data", "delete my personal", "erase my data", "data deletion", "data export", "download my data")),
    ("security", ("password", "forgot my password", "reset my password", "otp", "one-time code", "account hacked", "account compromised", "can't log in", "cannot log in", "login", "sign in", "two-factor", "authentication code")),
    ("cancellation", ("cancel order", "cancel my order", "cancel this order", "cancellation", "stop my order", "withdraw my order")),
    ("refund", ("refund", "money back", "money hasn't come back", "money has not come back", "money not returned", "refund status", "credited back", "reimbursement")),
    ("return", ("return", "send this back", "send it back", "send back", "give it back", "wrong product", "wrong item", "damaged product", "arrived damaged", "replacement")),
    ("shipping", ("shipping", "delivery", "deliver", "package", "parcel", "tracking", "track my", "where is my order", "where is my", "where is", "out for delivery", "delivery delay", "late delivery", "hasn't arrived", "has not arrived")),
    ("payment", ("payment", "paid", "charge", "charged", "upi", "credit card", "debit card", "cash on delivery", "cod", "transaction", "payment failed", "failed payment")),
    ("warranty", ("warranty", "covered", "coverage", "repair", "manufacturer defect", "service center")),
    ("promotion", ("coupon", "promo", "promotion", "discount", "offer", "deal", "membership tier", "loyalty tier", "member benefit")),
    ("product", ("product", "specification", "specs", "feature", "compatible", "compatibility", "hdmi", "usb-c", "battery life", "screen size", "does the", "does this", "compare")),
    ("order", ("order", "purchase", "invoice", "receipt", "order number")),
]
_ALLOWED = {"refund", "return", "cancellation", "shipping", "payment", "warranty", "promotion", "security", "privacy", "product", "order", "general"}


def route_query(user_query: str) -> str:
    """Return one supported category; deterministic rules take precedence."""
    query = re.sub(r"\s+", " ", (user_query or "").casefold()).strip()
    if re.search(r"\b(?:send|ship|post|take)\b.{0,45}\bback\b", query):
        return "return"
    for category, phrases in _RULES:
        if any(phrase in query for phrase in phrases):
            return category
    if re.search(r"\bORD-\d{5}\b", query, re.IGNORECASE):
        return "order"

    prompt = f"""Classify this customer-service question into exactly one category.
Question: {user_query}
Categories: refund, return, cancellation, shipping, payment, warranty, promotion, security, privacy, product, order, general
Return only the category name."""
    if not ollama_available():
        return "general"
    try:
        result = llm.invoke(prompt)
        candidate = strip_internal_reasoning(getattr(result, "content", "")).lower()
        candidate = re.sub(r"[^a-z]+", "", candidate)
        if candidate in _ALLOWED:
            return candidate
    except Exception:
        pass
    return "general"
