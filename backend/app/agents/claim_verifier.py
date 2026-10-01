"""Evidence-bound claim verifier with exact comparisons for high-risk facts."""

import re


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").casefold()).strip()


def _all_evidence_text(evidence: list[dict]) -> str:
    parts = []
    for item in evidence or []:
        parts.append(str(item.get("text", "")))
        if item.get("structured_data") is not None:
            parts.append(str(item["structured_data"]))
    return "\n".join(parts)


def _result(claim: dict, status: str, reason: str):
    return {**claim, "verification": status, "verification_reason": reason}


def _time_limit_status(claim: dict, evidence_text: str):
    subject = str(claim.get("subject", "refund")).casefold()
    value = str(claim.get("value", ""))
    numbers = re.findall(r"\d+", value)
    if not numbers:
        numbers = re.findall(r"\d+", str(claim.get("claim", "")))
    if not numbers:
        return "UNSUPPORTED", "The response states a time limit that could not be parsed."
    subject_pattern = r"returns?" if subject.startswith("return") else r"refunds?"
    claim_processing = bool(re.search(r"\b(?:process(?:ed|ing)?|completion|after approval)\b", str(claim.get("claim", "")), re.IGNORECASE))
    relevant = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", evidence_text):
        if not re.search(subject_pattern, sentence, re.IGNORECASE):
            continue
        policy_processing = bool(re.search(r"\b(?:process(?:ed|ing)?|completion|after approval)\b", sentence, re.IGNORECASE))
        if policy_processing != claim_processing:
            continue
        ranges = re.findall(r"\b(\d+)\s*[-–]\s*(\d+)\s*(?:calendar\s+|business\s+)?days?", sentence, re.IGNORECASE)
        if ranges:
            relevant.extend([low for low, _ in ranges] + [high for _, high in ranges])
        else:
            relevant.extend(re.findall(r"\b(\d+)\s*(?:calendar\s+|business\s+)?days?", sentence, re.IGNORECASE))
    if all(number in relevant for number in numbers):
        return "VERIFIED", "The time limit matches a trusted policy source."
    if relevant:
        return "CONTRADICTED", "The stated time limit differs from the trusted policy limit."
    return "UNSUPPORTED", "No relevant time limit was found in trusted evidence."


def _refund_processing_status(claim: dict, evidence_text: str):
    claimed = re.findall(r"\d+", str(claim.get("value", "")))
    relevant = re.findall(r"(?:approved\s+)?refunds?.{0,100}?(?:processed|processing).{0,60}?(\d+)\s*[-–]\s*(\d+)\s*(?:business\s+)?days?", evidence_text, re.IGNORECASE)
    if len(claimed) >= 2 and any(claimed[0] == low and claimed[1] == high for low, high in relevant):
        return "VERIFIED", "The refund processing range matches trusted policy evidence."
    if relevant:
        return "CONTRADICTED", "The refund processing range differs from trusted policy evidence."
    return "UNSUPPORTED", "No refund processing range was found in trusted policy evidence."


def _verify_one(claim: dict, evidence_text: str):
    kind = str(claim.get("type", "other")).casefold()
    text = str(claim.get("claim", ""))
    value = str(claim.get("value", "") or "")
    lower_evidence = normalize(evidence_text)
    lower_claim = normalize(text)

    if kind == "security" and value == "disclosure_requested":
        return "CONTRADICTED", "Trusted security policy prohibits requesting authentication secrets."
    if kind == "time_limit":
        return _time_limit_status(claim, evidence_text)
    if kind == "refund_processing":
        return _refund_processing_status(claim, evidence_text)

    if kind == "shipping_guarantee":
        if re.search(r"delivery.{0,100}(?:not guaranteed|estimate|estimated)", lower_evidence):
            return "CONTRADICTED", "Trusted shipping policy treats delivery dates as estimates."
        return "UNSUPPORTED", "No trusted delivery guarantee supports this claim."

    if kind in {"money", "refund_amount"}:
        amount = re.sub(r"[^\d.]", "", value)
        evidence_amounts = {re.sub(r",", "", match) for match in re.findall(r"(?:₹\s*|INR\s*)([\d,]+(?:\.\d{1,2})?)", evidence_text, re.IGNORECASE)}
        evidence_amounts.update(re.sub(r",", "", match) for match in re.findall(r"[\"']?(?:amount|total_amount|unit_price|price)[\"']?\s*:\s*[\"']?([\d,]+(?:\.\d{1,2})?)", evidence_text, re.IGNORECASE))
        if amount and amount in evidence_amounts:
            return "VERIFIED", "The amount matches a trusted record or source."
        if any(word in lower_evidence for word in ("refund", "payment", "total_amount", "amount")):
            return "CONTRADICTED", "The stated amount does not match the available transaction evidence."
        return "UNSUPPORTED", "No trusted amount supports this claim."

    if kind == "tracking_number":
        if value.casefold() in lower_evidence:
            return "VERIFIED", "The tracking number matches a trusted shipment record."
        if "tracking_number" in lower_evidence or "tracking number" in lower_evidence:
            return "CONTRADICTED", "The tracking number differs from the trusted shipment record."
        return "UNSUPPORTED", "No trusted shipment record supports this tracking number."

    if kind == "approval_status":
        status = value.casefold()
        if status and status in lower_evidence and "exception" in lower_evidence:
            return "VERIFIED", "The approval status matches a trusted case record."
        if "exception" in lower_evidence or "appeal" in lower_evidence:
            return "CONTRADICTED", "The approval status differs from the available case record."
        return "UNSUPPORTED", "No authorized case record confirms this approval status."

    if kind == "order_status":
        status = value.casefold()
        order_id = str(claim.get("subject", "order")).casefold()
        status_evidence = lower_evidence.replace("in_transit", "in transit").replace("in-transit", "in transit")
        if status and status in status_evidence and (order_id == "order" or order_id in lower_evidence):
            return "VERIFIED", "The order status matches structured order evidence."
        statuses = ("processing", "shipped", "in_transit", "out_for_delivery", "delivered", "cancelled", "payment_failed", "returned", "refunded")
        if any(f"'{state}'" in lower_evidence or f"\"{state}\"" in lower_evidence for state in statuses):
            return "CONTRADICTED", "The stated order status differs from the available order record."
        return "UNSUPPORTED", "No order status is available in trusted evidence."

    if kind == "warranty":
        digits = re.findall(r"\d+", value)
        if digits and value.casefold() in lower_evidence:
            return "VERIFIED", "The warranty period matches product evidence."
        if digits and any(token in lower_evidence for token in ("warranty_period", "warranty period", "warranty")):
            return "CONTRADICTED", "The stated warranty period differs from product evidence."
        return "UNSUPPORTED", "No product-specific warranty period supports the claim."

    if kind == "date":
        date_value = value
        if date_value.casefold() in lower_evidence:
            return "VERIFIED", "The date appears in a trusted source."
        if any(word in lower_claim for word in ("delivery", "refund", "return", "order", "payment")):
            return "CONTRADICTED", "The date does not match the available structured record."
        return "UNSUPPORTED", "No trusted source supports this date."

    if kind in {"shipping_time", "shipping"}:
        numeric_tokens = re.findall(r"\d+", value or text)
        if len(numeric_tokens) >= 2 and re.search(rf"\b{numeric_tokens[0]}\s*[-–]\s*{numeric_tokens[1]}\s*(?:business\s+)?days?", evidence_text, re.IGNORECASE):
            return "VERIFIED", "The shipping range matches a trusted policy source."
        if numeric_tokens and any(word in lower_evidence for word in ("business days", "delivery estimate", "delivery generally")):
            return "CONTRADICTED", "The shipping time differs from the trusted estimate."
        return "UNSUPPORTED", "No trusted shipping estimate supports the claim."

    # Broader semantic claims use substantial term overlap, never as the only
    # check for high-risk values handled above.
    terms = [token for token in re.findall(r"[a-z0-9]+", lower_claim) if len(token) > 4]
    if terms and sum(token in lower_evidence for token in terms) / len(terms) >= 0.72:
        return "VERIFIED", "The claim is consistent with the retrieved trusted evidence."
    return "UNSUPPORTED", "The claim could not be tied to trusted evidence."


def verify_claims(claims: list, evidence: list) -> dict:
    """Label each claim VERIFIED, UNSUPPORTED, or CONTRADICTED."""
    if not claims:
        return {"decision": "APPROVE", "risk": "LOW", "verified_claims": [], "unsupported_claims": [], "contradicted_claims": [], "results": [], "reason": "No significant claims were extracted."}

    evidence_text = _all_evidence_text(evidence)
    results = []
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        status, reason = _verify_one(claim, evidence_text)
        results.append(_result(claim, status, reason))
    verified = [item for item in results if item["verification"] == "VERIFIED"]
    unsupported = [item for item in results if item["verification"] == "UNSUPPORTED"]
    contradicted = [item for item in results if item["verification"] == "CONTRADICTED"]
    if contradicted:
        decision, risk, reason = "CORRECT", "HIGH", "One or more claims conflict with trusted evidence."
    elif unsupported:
        decision, risk, reason = "CORRECT", "MEDIUM", "One or more claims are not supported by trusted evidence."
    else:
        decision, risk, reason = "APPROVE", "LOW", "All extracted claims are supported by trusted evidence."
    return {"decision": decision, "risk": risk, "verified_claims": verified, "unsupported_claims": unsupported, "contradicted_claims": contradicted, "results": results, "reason": reason}
