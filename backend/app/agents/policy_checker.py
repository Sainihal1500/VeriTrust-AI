"""Deterministic high-risk policy and safety checks for Maker responses."""

import re


def extract_numbers_with_context(text: str):
    source = text or ""
    return [(match.group(), source[max(0, match.start() - 80):match.end() + 80]) for match in re.finditer(r"\b\d+(?:,\d{3})*(?:\.\d{1,2})?\b", source)]


def extract_day_limits(text: str):
    return [int(match.group(1)) for match in re.finditer(r"\b(\d+)\s*(?:calendar\s+|business\s+)?days?\b", (text or "").casefold())]


def contains_any(text: str, phrases: list[str]):
    lower = (text or "").casefold()
    return any(phrase.casefold() in lower for phrase in phrases)


def _evidence_text(evidence: list[dict]) -> str:
    return "\n".join(str(item.get("text", "")) for item in evidence or [])


def check_numeric_contradictions(draft_response: str, policy_text: str):
    def day_rules(text: str):
        rules = []
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", text or ""):
            sentence = sentence.casefold()
            subject = "return" if "return" in sentence else ("refund" if "refund" in sentence else None)
            if not subject:
                continue
            processing = bool(re.search(r"\b(?:process(?:ed|ing)?|completion|after approval)\b", sentence))
            ranges = re.findall(r"\b(\d+)\s*[-–]\s*(\d+)\s*(?:calendar\s+|business\s+)?days?", sentence)
            if ranges:
                rules.extend((subject, processing, (int(low), int(high))) for low, high in ranges)
                continue
            for match in re.finditer(r"\b(?:within|up to|after|more than|no later than)\s+(\d+)\s*(?:calendar\s+|business\s+)?days?", sentence):
                rules.append((subject, processing, (int(match.group(1)), int(match.group(1)))))
        return rules

    response, policy = (draft_response or "").casefold(), policy_text or ""
    contradiction = []
    policy_rules = day_rules(policy)
    for subject, processing, values in day_rules(response):
        relevant = [rule[2] for rule in policy_rules if rule[0] == subject and rule[1] == processing]
        if relevant and values not in relevant:
            descriptor = "processing" if processing else "eligibility"
            contradiction.append(f"Maker used a {values[0]}-{values[1]} day {subject} {descriptor} window; trusted policy specifies {relevant}.")
    return list(dict.fromkeys(contradiction))


def check_cancellation_contradictions(draft_response: str, policy_text: str):
    policy, draft = (policy_text or "").casefold(), (draft_response or "").casefold()
    restriction = "cancel" in policy and bool(re.search(r"\b(?:once|after)\b.{0,60}\b(?:shipped|shipment|shipping)\b", policy))
    claim = bool(re.search(r"\bcancel\b.{0,80}\b(?:after|once)\b.{0,30}\b(?:shipped|shipment|shipping)\b", draft))
    return ["Maker says an order can be cancelled after shipment, which conflicts with the cancellation policy."] if restriction and claim else []


def check_security_contradictions(draft_response: str, policy_text: str):
    del policy_text  # The rule is absolute, even if retrieval failed.
    text = (draft_response or "").casefold()
    patterns = (
        r"\b(?:share|send|tell|provide|read|give)\s+(?:me\s+|support\s+)?(?:your\s+)?(?:otp|one[- ]time (?:password|code)|password|verification code)\b",
        r"\b(?:otp|one[- ]time (?:password|code)|password|verification code)\b.{0,35}\b(?:share|send|tell|provide|read|give)\b",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            sentence_start = max(text.rfind(".", 0, match.start()), text.rfind("!", 0, match.start()), text.rfind("?", 0, match.start()), text.rfind("\n", 0, match.start())) + 1
            sentence_end = min((position for position in (text.find(".", match.end()), text.find("!", match.end()), text.find("?", match.end()), text.find("\n", match.end())) if position >= 0), default=len(text))
            sentence = text[sentence_start:sentence_end]
            safe_instruction = re.search(r"\b(?:never|do not|don't|should not|shouldn't|must not|mustn't)\b.{0,60}\b(?:share|send|tell|provide|read|give)\b", sentence)
            if safe_instruction:
                continue
            return ["Maker requests an authentication secret such as a password or one-time code."]
    return []


def check_guarantee_contradictions(draft_response: str, policy_text: str):
    draft, policy = (draft_response or "").casefold(), (policy_text or "").casefold()
    has_guarantee = bool(re.search(r"\b(?:guaranteed|guarantee|will definitely arrive|certainly arrive)\b", draft))
    policy_estimate = any(term in policy for term in ("delivery times are estimates", "delivery is an estimate", "not guaranteed", "delivery estimates"))
    if has_guarantee and policy_estimate and any(term in draft for term in ("delivery", "arrive", "shipping")):
        return ["Maker presents delivery timing as guaranteed while the trusted shipping policy gives estimates."]
    return []


def check_refund_promises(draft_response: str, policy_text: str):
    draft, policy = (draft_response or "").casefold(), (policy_text or "").casefold()
    unconditional = "refund" in draft and bool(re.search(r"\b(?:you will receive|you are guaranteed|definitely receive|refund is guaranteed|guaranteed refund)\b", draft))
    conditional_policy = any(term in policy for term in ("subject to eligibility", "subject to approval", "eligibility review", "eligibility requirements", "cannot be guaranteed", "refund eligibility"))
    return ["Maker makes an unconditional refund promise although policy requires an eligibility check."] if unconditional and conditional_policy else []


def check_payment_promises(draft_response: str, evidence: list[dict]):
    draft = (draft_response or "").casefold()
    if not any(word in draft for word in ("payment", "charged", "refund", "credited")):
        return []
    # Specific money/date claims are checked by claim_verifier. This catches
    # unconditional completion promises independently of model output.
    if re.search(r"\b(?:will be|has been) credited (?:today|immediately|within \d+ hours?)\b", draft):
        text = _evidence_text(evidence).casefold()
        if not any(term in text for term in ("processed_at", "estimated_completion", "completed", "credited")):
            return ["Maker promises a transaction completion time without a supporting transaction record."]
    return []


def check_policy_contradictions(draft_response: str, evidence: list, claim_verification: dict | None = None):
    policy_text = _evidence_text(evidence)
    security = check_security_contradictions(draft_response, policy_text)
    contradictions = []
    for checker, args in (
        (check_numeric_contradictions, (draft_response, policy_text)),
        (check_cancellation_contradictions, (draft_response, policy_text)),
        (check_guarantee_contradictions, (draft_response, policy_text)),
        (check_refund_promises, (draft_response, policy_text)),
        (check_payment_promises, (draft_response, evidence)),
    ):
        contradictions.extend(checker(*args))
    if claim_verification:
        contradictions.extend(item.get("claim", "Unsupported claim") for item in claim_verification.get("contradicted_claims", []))

    contradictions = list(dict.fromkeys(contradictions))
    if security:
        return {"decision": "BLOCK", "risk": "HIGH", "reason": "The response violates an authentication-secret safety rule.", "contradicted_claims": security}
    if contradictions:
        return {"decision": "CORRECT", "risk": "HIGH", "reason": "The response contains claims that conflict with policy or structured evidence.", "contradicted_claims": contradictions}
    if claim_verification and claim_verification.get("unsupported_claims"):
        unsupported = claim_verification["unsupported_claims"]
        high_impact = {"time_limit", "refund_processing", "shipping", "shipping_time", "shipping_guarantee", "date", "money", "refund_amount", "order_status", "tracking_number", "warranty", "payment", "eligibility", "approval_status"}
        decision = "REVIEW" if any(item.get("type") in high_impact for item in unsupported) else "CORRECT"
        return {"decision": decision, "risk": "MEDIUM" if decision == "REVIEW" else "HIGH", "reason": "A high-impact claim needs an authorized record or policy source." if decision == "REVIEW" else "One or more claims are not supported by trusted evidence.", "contradicted_claims": [item.get("claim", "Unsupported claim") for item in unsupported]}
    return {"decision": "APPROVE", "risk": "LOW", "reason": "No deterministic policy contradiction detected.", "contradicted_claims": []}
