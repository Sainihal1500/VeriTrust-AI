"""Extract factual claims, with deterministic coverage for high-risk facts."""

import json
import os
import re

from langchain_ollama import ChatOllama
from agents.llm_utils import ollama_available, strip_internal_reasoning

llm = ChatOllama(model=os.getenv("VERITRUST_CHAT_MODEL", "qwen3.5:latest"), temperature=0, num_predict=384, base_url=os.getenv("OLLAMA_BASE_URL") or None, client_kwargs={"timeout": 20})


def _claim(text: str, claim_type: str, subject: str, value=None):
    return {"claim": text.strip(), "type": claim_type, "subject": subject, "value": value, "source": "rule"}


def rule_based_claims(response: str) -> list[dict]:
    text = response or ""
    lower = text.casefold()
    claims = []

    for match in re.finditer(r"\b(?:approved\s+)?refunds?\b.{0,100}?\b(?:processed|processing)\b.{0,60}?\b(\d+)\s*[-–]\s*(\d+)\s*(business\s+)?days?", lower):
        claims.append(_claim(match.group(0), "refund_processing", "refund_processing", f"{match.group(1)}-{match.group(2)} business days"))
    for match in re.finditer(r"\b(?:approved\s+)?refunds?\b.{0,100}?\b(?:processed|processing)\b.{0,60}?\b(\d+)(?!\s*[-–]\s*\d+)\s*(business\s+)?days?", lower):
        claims.append(_claim(match.group(0), "refund_processing", "refund_processing", f"{match.group(1)}-{match.group(1)} business days"))

    for match in re.finditer(r"\b(refunds?|returns?)\b.{0,100}?\b(?:within|up to|after)\s+(\d+)\s*(calendar\s+|business\s+)?days?", lower):
        subject = "refund" if match.group(1).startswith("refund") else "return"
        unit = match.group(3).strip() if match.group(3) else "calendar"
        value = f"{match.group(2)} {unit} days"
        claims.append(_claim(match.group(0), "time_limit", subject, value))

    for match in re.finditer(r"\b(\d+)\s*(?:calendar\s+|business\s+)?days?\b.{0,60}?\b(refund|return)", lower):
        subject = match.group(2)
        claims.append(_claim(match.group(0), "time_limit", subject, f"{match.group(1)} days"))

    for match in re.finditer(r"\b(?:guarantee(?:d)?|will definitely arrive)\b.{0,90}?\b(?:delivery|arrive|shipping)\b.{0,40}?\b(\d+)\s*(business\s+)?days?", lower):
        claims.append(_claim(match.group(0), "shipping_guarantee", "delivery", f"{match.group(1)} days"))
    for match in re.finditer(r"\b(?:delivery|shipping|arrive)\b.{0,60}?\b(\d+)\s*[-–]\s*(\d+)\s*(business\s+)?days?", lower):
        claims.append(_claim(match.group(0), "shipping_time", "delivery", f"{match.group(1)}-{match.group(2)} days"))

    secret_request = False
    secret_patterns = (
        r"\b(?:share|send|tell|provide|read|give)\b.{0,35}\b(?:otp|one[- ]time (?:password|code)|password|verification code)\b",
        r"\b(?:otp|one[- ]time (?:password|code)|password|verification code)\b.{0,35}\b(?:share|send|tell|provide|read|give)\b",
    )
    for pattern in secret_patterns:
        for match in re.finditer(pattern, lower):
            sentence_start = max(lower.rfind(".", 0, match.start()), lower.rfind("!", 0, match.start()), lower.rfind("?", 0, match.start()), lower.rfind("\n", 0, match.start())) + 1
            sentence_end = min((position for position in (lower.find(".", match.end()), lower.find("!", match.end()), lower.find("?", match.end()), lower.find("\n", match.end())) if position >= 0), default=len(lower))
            sentence = lower[sentence_start:sentence_end]
            safe_instruction = re.search(r"\b(?:never|do not|don't|should not|shouldn't|must not|mustn't)\b.{0,60}\b(?:share|send|tell|provide|read|give)\b", sentence)
            if safe_instruction:
                continue
            secret_request = True
    if secret_request:
        claims.append(_claim("The response asks the customer to disclose an authentication secret.", "security", "authentication", "disclosure_requested"))

    for match in re.finditer(r"\b(?:₹|inr\s*)([\d,]+(?:\.\d{1,2})?)\b|\b([\d,]+(?:\.\d{1,2})?)\s*(?:inr|rupees?)\b", lower):
        amount = (match.group(1) or match.group(2)).replace(",", "")
        context = lower[max(0, match.start() - 90):min(len(lower), match.end() + 70)]
        if any(term in context for term in ("refund", "payment", "charged", "cost", "price", "amount", "order")):
            claims.append(_claim(match.group(0), "money", "amount", amount))

    for match in re.finditer(r"\b(?:order\s+)?(ORD-\d{5})\b.{0,80}?\b(confirmed|processing|shipped|in[_ -]transit|out for delivery|delivered|cancelled|canceled|returned|refunded|payment failed|completed|approved|requested)\b|\byour order\b.{0,35}?\b(confirmed|processing|shipped|in[_ -]transit|out for delivery|delivered|cancelled|canceled|returned|refunded|payment failed|completed|approved|requested)\b", text, re.IGNORECASE):
        order_id = next((group for group in match.groups() if group and group.upper().startswith("ORD-")), None)
        status = next((group for group in match.groups() if group and group.casefold() in {"confirmed", "processing", "shipped", "in transit", "in-transit", "in_transit", "out for delivery", "delivered", "cancelled", "canceled", "returned", "refunded", "payment failed", "completed", "approved", "requested"}), None)
        if status:
            claims.append(_claim(match.group(0), "order_status", order_id or "order", status.casefold().replace("canceled", "cancelled").replace("_", " ").replace("-", " ")))

    for match in re.finditer(r"\b(TRK-[A-Z0-9-]+)\b", text, re.IGNORECASE):
        claims.append(_claim(f"Tracking number is {match.group(1).upper()}.", "tracking_number", "shipment", match.group(1).upper()))

    approval_match = re.search(r"\b(exception|appeal|supervisor review|specialist review)\b.{0,60}\b(approved|accepted|rejected|denied|pending)\b|\b(approved|accepted|rejected|denied|pending)\b.{0,60}\b(exception|appeal|supervisor review|specialist review)\b", text, re.IGNORECASE)
    if approval_match:
        status = next((group for group in approval_match.groups() if group and group.casefold() in {"approved", "accepted", "rejected", "denied", "pending"}), "unknown")
        claims.append(_claim(approval_match.group(0), "approval_status", "exception", status.casefold()))

    for match in re.finditer(r"\b(?:warranty|covered)\b.{0,80}?\b(\d+)\s*(year|month)s?\b|\b(\d+)\s*(year|month)s?\s+(?:limited\s+)?warranty\b", lower):
        count = match.group(1) or match.group(3)
        unit = match.group(2) or match.group(4)
        plural = "s" if count != "1" else ""
        claims.append(_claim(match.group(0), "warranty", "warranty_period", f"{count} {unit}{plural}"))

    for match in re.finditer(r"\b(?:20\d{2}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/20\d{2})\b", text):
        context = text[max(0, match.start() - 80):min(len(text), match.end() + 80)]
        if any(word in context.casefold() for word in ("delivery", "refund", "return", "order", "payment", "date", "arrive")):
            claims.append(_claim(context.strip(), "date", "date", match.group(0)))
    return claims


def llm_claims(response: str) -> list[dict]:
    """Ask local Qwen for semantic claims; malformed/unavailable output is ignored."""
    if not ollama_available():
        return []
    prompt = f"""Extract factual claims made in this customer-service response.
Response: {response}
Return only JSON: {{"claims":[{{"claim":"short claim","type":"policy|eligibility|payment|product|promotion|other","subject":"topic","value":null}}]}}
Do not include greetings or opinions."""
    try:
        result = llm.invoke(prompt)
        raw = strip_internal_reasoning(getattr(result, "content", ""))
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE)
        parsed = json.loads(raw)
        claims = parsed.get("claims", [])
        if not isinstance(claims, list):
            return []
        return [dict(item, source="llm") for item in claims if isinstance(item, dict) and item.get("claim")]
    except Exception:
        return []


def remove_duplicate_claims(claims: list[dict]) -> list[dict]:
    unique, seen = [], set()
    for item in claims:
        if not isinstance(item, dict) or not str(item.get("claim", "")).strip():
            continue
        key = (str(item.get("type", "other")).casefold(), re.sub(r"\W+", " ", str(item["claim"]).casefold()).strip())
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def extract_claims(response: str, use_llm: bool = True) -> list[dict]:
    if not response or not response.strip():
        return []
    claims = rule_based_claims(response)
    if use_llm:
        claims.extend(llm_claims(response))
    return remove_duplicate_claims(claims)
