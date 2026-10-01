"""FastAPI service for the VeriTrust customer-support graph."""

from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
import uuid

import chromadb
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agents.claim_extractor import extract_claims
from agents.claim_verifier import verify_claims
from agents.judge import judge_agent
from agents.policy_checker import check_policy_contradictions
from audit import get_audit_event, get_metrics, list_recent_audit, record_audit_event
from database.account_service import get_customer_order_information, get_order_information, get_order_transaction_information
from database.customer_data import CUSTOMERS, ORDERS
from database.transaction_data import PAYMENTS, REFUNDS, RETURNS, SHIPMENTS
from security.session import get_session_customer
from workflows.veritrust_graph import invoke_veritrust


PROJECT_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIR = PROJECT_ROOT / "frontend"
KNOWLEDGE_BASE_DIR = PROJECT_ROOT / "backend" / "data" / "knowledge_base"
CHROMA_DIR = PROJECT_ROOT / "backend" / "data" / "chroma"

app = FastAPI(title="VeriTrust AI", version="1.0.0", description="Dual-agent customer-service verification platform")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str = Field(min_length=1, max_length=4000)


class VerifyRequest(BaseModel):
    session_id: str | None = None
    message: str = Field(min_length=1, max_length=4000)
    response: str = Field(min_length=1, max_length=4000)


def _source_ids(sources: list[dict]):
    return [{key: item.get(key) for key in ("source", "document_id", "category", "version", "effective_date", "source_type", "distance", "similarity_score", "category_match", "type") if item.get(key) is not None} for item in sources]


def _audit_workflow(result: dict, session_id: str | None, message: str, request_type: str = "chat", maker_response: str | None = None, final_response: str | None = None, claims: list | None = None, verification: dict | None = None, policy_check: dict | None = None, decision: str | None = None, risk: str | None = None):
    sources = result.get("sources", [])
    account_sources = [item for item in sources if item.get("source_type") == "trusted_structured_database"]
    event = {
        "request_id": result.get("request_id") or str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "customer_id": result.get("authenticated_customer_id"),
        "user_query": message,
        "query_category": result.get("query_category"),
        "retrieved_sources": [item for item in sources if item.get("source_type") != "trusted_structured_database"],
        "account_sources": account_sources,
        "maker_response": maker_response if maker_response is not None else result.get("draft_response"),
        "claims": claims if claims is not None else result.get("claims", []),
        "claim_verification": verification if verification is not None else {"initial": result.get("claim_verification", {}), "final": result.get("final_claim_verification", {})},
        "policy_check": policy_check if policy_check is not None else {"initial": result.get("policy_check", {}), "final": result.get("final_policy_check", {})},
        "judge_decision": {"initial": result.get("judgment", {}), "final": result.get("final_judgment", result.get("judgment", {}))},
        "decision": decision or result.get("decision", "REVIEW"),
        "risk": risk or result.get("risk", "MEDIUM"),
        "corrected_response": result.get("corrected_response"),
        "final_response": final_response if final_response is not None else result.get("final_response"),
        "latency_ms": result.get("latency_ms", 0),
        "security_result": result.get("security_result", {}),
        "node_latency_ms": result.get("node_latency_ms", {}),
        "request_type": request_type,
    }
    return record_audit_event(event)


def _try_audit(*args, **kwargs):
    try:
        return _audit_workflow(*args, **kwargs)
    except Exception:
        return None


@app.get("/health")
def health():
    try:
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        count = client.get_collection("veritrust_knowledge").count()
    except Exception:
        count = 0
    return {
        "status": "ok",
        "service": "veritrust-ai",
        "knowledge_base_documents": len(list(KNOWLEDGE_BASE_DIR.rglob("*.txt"))),
        "knowledge_base_chunks": count,
        "dataset": {
            "customers": len(CUSTOMERS), "orders": len(ORDERS), "payments": len(PAYMENTS),
            "refunds": len(REFUNDS), "returns": len(RETURNS), "shipments": len(SHIPMENTS),
        },
    }


@app.post("/chat")
def chat(request: ChatRequest):
    started = perf_counter()
    request_id = str(uuid.uuid4())
    try:
        result = invoke_veritrust(request.message, request.session_id, request_id)
    except Exception:
        result = {
            "request_id": request_id, "query_category": "general", "decision": "REVIEW", "risk": "MEDIUM",
            "draft_response": "", "final_response": "I can’t verify that request right now. Please try again or contact VeriCommerce support.",
            "sources": [], "evidence": [], "account_evidence": [], "security_result": {"status": "ERROR", "authorized": False},
            "authenticated_customer_id": get_session_customer(request.session_id), "node_latency_ms": {},
        }
    result.setdefault("latency_ms", round((perf_counter() - started) * 1000, 3))
    audit = _try_audit(result, request.session_id, request.message)
    return {
        "request_id": result["request_id"],
        "response": result.get("final_response", "I can’t verify that request right now."),
        "decision": result.get("decision", "REVIEW"),
        "risk": result.get("risk", "MEDIUM"),
        "reason": (result.get("final_judgment") or result.get("judgment") or {}).get("reason", "Verification completed."),
        "category": result.get("query_category", "general"),
        "security_status": result.get("security_result", {}).get("status", "UNKNOWN"),
        "sources": result.get("sources", []),
        "verification_status": result.get("decision", "REVIEW"),
        "audit_recorded": audit is not None,
        "latency_ms": result["latency_ms"],
    }


@app.post("/verify")
def verify(request: VerifyRequest):
    started = perf_counter()
    request_id = str(uuid.uuid4())
    try:
        context = invoke_veritrust(request.message, request.session_id, request_id)
    except Exception:
        context = {"request_id": request_id, "decision": "REVIEW", "risk": "MEDIUM", "final_response": "", "sources": [], "evidence": [], "account_evidence": [], "security_result": {"status": "ERROR", "authorized": False}, "node_latency_ms": {}}
    if context.get("decision") == "BLOCK" or not context.get("security_result", {}).get("authorized", True):
        audit = _try_audit(context, request.session_id, request.message, "verify", request.response, "Verification was blocked because account access could not be verified.", decision="BLOCK", risk="HIGH")
        return {"request_id": request_id, "decision": "BLOCK", "risk": "HIGH", "reason": "The request could not be verified for this session.", "claims": [], "sources": context.get("sources", []), "security_status": context.get("security_result", {}).get("status", "UNKNOWN"), "audit_recorded": audit is not None, "latency_ms": round((perf_counter() - started) * 1000, 3)}

    evidence = context.get("evidence", []) + context.get("account_evidence", [])
    claims = extract_claims(request.response)
    claim_result = verify_claims(claims, evidence)
    policy_result = check_policy_contradictions(request.response, evidence, claim_result)
    judgment = judge_agent(request.message, request.response, evidence, claim_result, policy_result)
    decision = judgment.get("decision", "REVIEW")
    risk = judgment.get("risk", "MEDIUM")
    audit = _try_audit(context, request.session_id, request.message, "verify", request.response, "Verification completed.", claims, claim_result, policy_result, decision, risk)
    return {
        "request_id": request_id, "decision": decision, "risk": risk,
        "reason": judgment.get("reason", "Verification completed."),
        "claims": claim_result.get("results", []),
        "claim_verification": claim_result,
        "policy_check": policy_result,
        "sources": context.get("sources", []),
        "security_status": context.get("security_result", {}).get("status", "UNKNOWN"),
        "audit_recorded": audit is not None,
        "latency_ms": round((perf_counter() - started) * 1000, 3),
    }


@app.get("/metrics")
def metrics():
    try:
        return get_metrics()
    except Exception:
        raise HTTPException(status_code=503, detail="Metrics are temporarily unavailable.")


@app.get("/audit/recent")
def recent_audit(session_id: str = Query(...), limit: int = Query(20, ge=1, le=100)):
    customer_id = get_session_customer(session_id)
    if not customer_id:
        raise HTTPException(status_code=401, detail="An authenticated session is required.")
    try:
        return {"events": list_recent_audit(session_id, limit)}
    except Exception:
        raise HTTPException(status_code=503, detail="Audit events are temporarily unavailable.")


@app.get("/audit/{request_id}")
def audit_detail(request_id: str, session_id: str = Query(...)):
    customer_id = get_session_customer(session_id)
    if not customer_id:
        raise HTTPException(status_code=401, detail="An authenticated session is required.")
    try:
        event = get_audit_event(request_id)
    except Exception:
        raise HTTPException(status_code=503, detail="Audit event is temporarily unavailable.")
    if not event or event.get("customer_id") != customer_id:
        raise HTTPException(status_code=404, detail="Audit event was not found.")
    return event


@app.get("/customer/{customer_id}/orders")
def customer_orders(customer_id: str, session_id: str = Query(...)):
    result = get_customer_order_information(customer_id, session_id)
    if not result.get("authorized"):
        raise HTTPException(status_code=404, detail="Customer records were not found.")
    return {"orders": [{key: order.get(key) for key in ("order_id", "product_name", "quantity", "total_amount", "currency", "order_date", "order_status", "payment_status", "estimated_delivery", "tracking_number")} for order in result.get("data", [])]}


@app.get("/order/{order_id}")
def order_detail(order_id: str, session_id: str = Query(...)):
    result = get_order_information(order_id, session_id)
    if not result.get("authorized"):
        raise HTTPException(status_code=404, detail="Order was not found.")
    order = result["data"]
    transactions = get_order_transaction_information(order_id, session_id)
    return {"order": {key: order.get(key) for key in ("order_id", "product_name", "quantity", "total_amount", "currency", "order_date", "order_status", "payment_status", "payment_method", "shipment_id", "tracking_number", "estimated_delivery", "actual_delivery", "cancellation_status", "return_status", "refund_status")}, "transactions": transactions.get("data", {})}


@app.get("/")
def frontend():
    index = FRONTEND_DIR / "index.html"
    if not index.exists():
        return {"service": "VeriTrust AI", "docs": "/docs"}
    return FileResponse(index)


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
