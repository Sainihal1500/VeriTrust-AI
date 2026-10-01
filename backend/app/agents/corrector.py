"""Rewrite Maker output using only trusted evidence and preserve safe content."""

import json
import os

from langchain_ollama import ChatOllama
from agents.maker import _fallback
from agents.llm_utils import ollama_available, strip_internal_reasoning

llm = ChatOllama(model=os.getenv("VERITRUST_CHAT_MODEL", "qwen3.5:latest"), temperature=0, num_predict=384, base_url=os.getenv("OLLAMA_BASE_URL") or None, client_kwargs={"timeout": 35})


def corrector_agent(user_query: str, maker_response: str, evidence: list, policy_check):
    if isinstance(policy_check, dict):
        policy_summary = policy_check
    else:
        policy_summary = str(policy_check)
    if not evidence:
        return "I can’t verify the requested details from the available records. Please contact VeriCommerce support for a review."
    sources = [{"source": item.get("source"), "document_id": item.get("document_id"), "version": item.get("version"), "effective_date": item.get("effective_date"), "type": item.get("source_type"), "evidence": item.get("structured_data", item.get("text", ""))} for item in evidence]
    prompt = f"""Rewrite the draft as a concise customer-facing response. Use only the trusted evidence. Remove every unsupported claim, incorrect number/date/amount/status, false guarantee, unsafe credential request, or unauthorized account detail. Keep accurate useful content from the draft. If the evidence cannot answer the question, say so and offer support review. Do not reveal reasoning.

CUSTOMER QUESTION: {user_query}
DRAFT: {maker_response}
VERIFICATION FINDINGS: {json.dumps(policy_summary, ensure_ascii=False, default=str)}
TRUSTED EVIDENCE: {json.dumps(sources, ensure_ascii=False, default=str)}

Return only the corrected customer-facing response."""
    if not ollama_available():
        return _fallback(user_query, evidence)
    try:
        result = llm.invoke(prompt)
        corrected = strip_internal_reasoning(getattr(result, "content", ""))
        if corrected:
            return corrected[:1600]
    except Exception:
        pass
    return _fallback(user_query, evidence)
