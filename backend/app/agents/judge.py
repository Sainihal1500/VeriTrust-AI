"""Independent structured Judge for customer-facing Maker responses."""

import json
import os
import re

from langchain_ollama import ChatOllama
from agents.llm_utils import ollama_available, strip_internal_reasoning

llm = ChatOllama(model=os.getenv("VERITRUST_CHAT_MODEL", "qwen3.5:latest"), temperature=0, num_predict=192, base_url=os.getenv("OLLAMA_BASE_URL") or None, client_kwargs={"timeout": 30})
_DECISIONS = {"APPROVE", "CORRECT", "REVIEW", "BLOCK"}


def _fallback(claim_verification: dict | None, policy_check: dict | None):
    policy = policy_check or {}
    verification = claim_verification or {}
    policy_decision = str(policy.get("decision", "APPROVE")).upper()
    verification_decision = str(verification.get("decision", "APPROVE")).upper()
    if policy_decision == "BLOCK":
        return {"decision": "BLOCK", "risk": "HIGH", "reason": policy.get("reason", "A security rule blocked this response."), "contradicted_claims": policy.get("contradicted_claims", [])}
    if policy_decision == "REVIEW" or verification_decision == "REVIEW":
        return {"decision": "REVIEW", "risk": "MEDIUM", "reason": policy.get("reason", verification.get("reason", "The available evidence needs support review.")), "contradicted_claims": policy.get("contradicted_claims", [])}
    if policy_decision == "CORRECT" or verification_decision == "CORRECT":
        items = policy.get("contradicted_claims", []) or verification.get("contradicted_claims", []) or verification.get("unsupported_claims", [])
        return {"decision": "CORRECT", "risk": max((policy.get("risk", "LOW"), verification.get("risk", "LOW")), key=lambda value: {"LOW": 0, "MEDIUM": 1, "HIGH": 2}.get(value, 0)), "reason": policy.get("reason", verification.get("reason", "The response needs correction.")), "contradicted_claims": items}
    return {"decision": "APPROVE", "risk": "LOW", "reason": "No unsupported or contradictory claims were identified.", "contradicted_claims": []}


def _parse_output(raw: str):
    raw = strip_internal_reasoning(raw)
    match = re.search(r"\{.*\}", raw or "", re.DOTALL)
    if not match:
        return None
    if not ollama_available():
        return deterministic
    try:
        parsed = json.loads(match.group(0))
        decision = str(parsed.get("decision", "")).upper()
        if decision not in _DECISIONS:
            return None
        risk = str(parsed.get("risk", "MEDIUM")).upper()
        if risk not in {"LOW", "MEDIUM", "HIGH"}:
            risk = "MEDIUM"
        claims = parsed.get("contradicted_claims", [])
        return {"decision": decision, "risk": risk, "reason": str(parsed.get("reason", "Judge completed verification."))[:320], "contradicted_claims": claims if isinstance(claims, list) else []}
    except (json.JSONDecodeError, TypeError, AttributeError):
        return None


def judge_agent(user_query: str, maker_response: str, evidence: list, claim_verification: dict | None = None, policy_check: dict | None = None):
    """Return APPROVE/CORRECT/REVIEW/BLOCK and a short auditable reason."""
    deterministic = _fallback(claim_verification, policy_check)
    if deterministic["decision"] in {"BLOCK", "CORRECT", "REVIEW"}:
        return deterministic

    sources = [
        {key: item.get(key) for key in ("source", "document_id", "version", "effective_date", "source_type", "text") if item.get(key) is not None}
        for item in (evidence or [])
    ]
    prompt = f"""Act as an independent customer-service answer verifier. Do not trust the Maker automatically.
Compare the query and response with the trusted evidence and verification results. Mark unsupported or contradicted material CORRECT; uncertain evidence REVIEW; serious security or privacy disclosure BLOCK; otherwise APPROVE. Give one concise reason, no chain-of-thought.
Return only JSON with keys decision, risk, reason, contradicted_claims.

QUERY: {user_query}
MAKER RESPONSE: {maker_response}
TRUSTED EVIDENCE: {json.dumps(sources, ensure_ascii=False, default=str)}
CLAIM VERIFICATION: {json.dumps(claim_verification or {}, ensure_ascii=False, default=str)}
POLICY CHECK: {json.dumps(policy_check or {}, ensure_ascii=False, default=str)}"""
    try:
        result = llm.invoke(prompt)
        parsed = _parse_output(str(getattr(result, "content", "") or ""))
        if parsed:
            # A model may raise risk or ask for correction, but may not
            # downgrade a deterministic safety decision.
            if parsed["decision"] == "BLOCK":
                return parsed
            return parsed
    except Exception:
        pass
    return deterministic
