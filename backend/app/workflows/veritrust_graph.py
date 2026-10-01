"""VeriTrust Maker/Judge LangGraph with a pre-retrieval session authorization gate."""

from time import perf_counter
from typing import Any, NotRequired, TypedDict
import json
import uuid

from langgraph.graph import END, StateGraph

from agents.account_router import route_account_query
from agents.claim_extractor import extract_claims
from agents.claim_verifier import verify_claims
from agents.corrector import corrector_agent
from agents.judge import judge_agent
from agents.maker import maker_agent
from agents.policy_checker import check_policy_contradictions
from agents.query_router import route_query
from database.account_service import (
    get_customer_information,
    get_customer_order_information,
    get_customer_transaction_information,
    get_order_information,
    get_order_transaction_information,
    get_product_information,
    get_promotion_information,
    get_support_case_information,
)
from database.customer_data import get_order
from database.support_data import get_support_case
from security.access_control import verify_customer_access, verify_order_access
from security.session import get_session_customer, is_authenticated
from rag.retriever import retrieve_evidence


class VeriTrustState(TypedDict, total=False):
    user_query: str
    session_id: NotRequired[str | None]
    authenticated_customer_id: NotRequired[str | None]
    request_id: NotRequired[str]
    query_category: str
    account_route: str
    order_id: str | None
    case_id: str | None
    requested_customer_id: str | None
    customer_id: str | None
    security_result: dict
    evidence: list[dict]
    account_evidence: list[dict]
    combined_evidence: list[dict]
    sources: list[dict]
    draft_response: str
    claims: list[dict]
    final_claims: list[dict]
    claim_verification: dict
    final_claim_verification: dict
    policy_check: dict
    final_policy_check: dict
    judgment: dict
    final_judgment: dict
    corrected_response: str
    final_response: str
    decision: str
    risk: str
    correction_performed: bool
    node_latency_ms: dict[str, float]
    security_blocked: bool
    retrieval_error: str | None


_SECURITY_REPLY = "I can’t verify that order or account for this session. Sign in to the account that placed the order or check the order ID, then try again."
_REVIEW_REPLY = "I can’t verify all of those details from the available records. VeriCommerce support can review this request."


def _timed(state: VeriTrustState, key: str, started: float):
    timings = dict(state.get("node_latency_ms", {}))
    timings[key] = round((perf_counter() - started) * 1000, 3)
    return timings


def query_router_node(state: VeriTrustState):
    started = perf_counter()
    category = route_query(state.get("user_query", ""))
    return {"query_category": category, "node_latency_ms": _timed(state, "routing", started)}


def account_router_node(state: VeriTrustState):
    started = perf_counter()
    result = route_account_query(state.get("user_query", ""), state.get("query_category"))
    return {
        "account_route": result["route"],
        "order_id": result["order_id"],
        "requested_customer_id": result["customer_id"],
        "case_id": result.get("case_id"),
        "node_latency_ms": _timed(state, "account_routing", started),
    }


def authentication_node(state: VeriTrustState):
    """Resolve identity from session and authorize requested private records."""
    session_id = state.get("session_id")
    route = state.get("account_route", "knowledge_base")
    requested_customer_id = state.get("requested_customer_id")
    private_routes = {"order_database", "customer_database", "account_database", "case_database"}

    if route not in private_routes:
        return {
            "authenticated_customer_id": get_session_customer(session_id) if is_authenticated(session_id) else None,
            "customer_id": None,
            "security_result": {"status": "PUBLIC", "authorized": True, "reason": "No private customer data is requested."},
            "security_blocked": False,
        }

    if not is_authenticated(session_id):
        return {
            "authenticated_customer_id": None,
            "security_result": {"status": "UNAUTHENTICATED", "authorized": False, "reason": "An authenticated session is required."},
            "security_blocked": True,
        }

    authenticated_customer_id = get_session_customer(session_id)
    customer_access = verify_customer_access(session_id, requested_customer_id)
    if not customer_access["allowed"]:
        return {
            "authenticated_customer_id": authenticated_customer_id,
            "security_result": {"status": "DENIED", "authorized": False, "reason": "Requested identity does not match the authenticated session."},
            "security_blocked": True,
        }

    if route == "order_database":
        order = get_order(state.get("order_id") or "")
        order_access = verify_order_access(session_id, order)
        if not order_access["allowed"]:
            known_but_denied = order is not None
            status = "DENIED" if known_but_denied else "ORDER_UNVERIFIED"
            return {
                "authenticated_customer_id": authenticated_customer_id,
                "customer_id": authenticated_customer_id,
                "security_result": {"status": status, "authorized": False, "reason": "Order could not be verified for the authenticated session."},
                "security_blocked": True,
            }

    if route == "case_database" and state.get("case_id"):
        case = get_support_case(state["case_id"])
        case_access = verify_customer_access(session_id, case.get("customer_id") if case else None)
        if not case or not case_access["allowed"]:
            status = "DENIED" if case else "RECORD_UNVERIFIED"
            return {
                "authenticated_customer_id": authenticated_customer_id,
                "customer_id": authenticated_customer_id,
                "security_result": {"status": status, "authorized": False, "reason": "Support case could not be verified for the authenticated session."},
                "security_blocked": True,
            }

    return {
        "authenticated_customer_id": authenticated_customer_id,
        # The query's ID is never used as the data lookup identity.
        "customer_id": authenticated_customer_id,
        "security_result": {"status": "AUTHORIZED", "authorized": True, "reason": "Authenticated session ownership verified."},
        "security_blocked": False,
    }


def security_response_node(state: VeriTrustState):
    status = state.get("security_result", {}).get("status")
    if status in {"DENIED", "UNAUTHENTICATED", "ORDER_UNVERIFIED", "RECORD_UNVERIFIED", "ERROR"}:
        response = _SECURITY_REPLY
    else:
        response = "For your safety, never share passwords, one-time codes, PINs, or payment security codes with support. Use the official VeriCommerce account recovery or payment support flow."
    return {
        "draft_response": response,
        "final_response": response,
        "decision": "BLOCK",
        "risk": "HIGH",
        "judgment": {"decision": "BLOCK", "risk": "HIGH", "reason": "Account data was not released because access could not be verified.", "contradicted_claims": []},
        "security_blocked": True,
    }


def retrieve_node(state: VeriTrustState):
    started = perf_counter()
    try:
        evidence = retrieve_evidence(state.get("user_query", ""), state.get("query_category", "general"), n_results=6)
        error = None
    except Exception as exc:
        evidence, error = [], type(exc).__name__
    return {"evidence": evidence, "retrieval_error": error, "node_latency_ms": _timed(state, "retrieval", started)}


def _record_evidence(source: str, evidence_type: str, result: dict):
    if not result.get("found"):
        return []
    return [{
        "text": json.dumps(result.get("data"), ensure_ascii=False, default=str),
        "source": source,
        "document_id": source,
        "category": "customer_data",
        "version": "live-demo",
        "effective_date": "current",
        "source_type": "trusted_structured_database",
        "distance": 0,
        "category_match": True,
        "type": evidence_type,
        "structured_data": result,
    }]


def account_data_node(state: VeriTrustState):
    """Fetch minimal private evidence only after authentication_node approves."""
    started = perf_counter()
    route = state.get("account_route", "knowledge_base")
    customer_id = state.get("authenticated_customer_id")
    session_id = state.get("session_id")
    category = state.get("query_category", "general")
    query = state.get("user_query", "").casefold()
    records: list[dict] = []

    # This guard stays in the data node as defense in depth against direct node use.
    if route in {"order_database", "customer_database", "account_database", "case_database"} and not state.get("security_result", {}).get("authorized"):
        return {"account_evidence": [], "node_latency_ms": _timed(state, "account_data", started)}

    if route == "order_database" and state.get("order_id"):
        order_result = get_order_information(state["order_id"], session_id)
        if order_result.get("found"):
            order = order_result["data"]
            # Omit the street address and unrelated customer fields from Maker context.
            visible_order = {key: order.get(key) for key in ("order_id", "product_id", "product_name", "quantity", "total_amount", "currency", "order_date", "order_status", "payment_status", "payment_method", "shipment_id", "tracking_number", "carrier", "estimated_delivery", "actual_delivery", "cancellation_status", "return_status", "refund_status")}
            if any(term in query for term in ("address", "ship to", "shipping address")):
                visible_order["shipping_address"] = order.get("shipping_address")
            records.extend(_record_evidence("customer_order_database", "order", {"found": True, "data": visible_order}))
            if category in {"product", "warranty"}:
                product_result = get_product_information(order.get("product_name", ""))
                records.extend(_record_evidence("vericommerce_product_catalog", "products", product_result))
            transactions = get_order_transaction_information(state["order_id"], session_id)
            summary = transactions.get("data", {}) if transactions.get("found") else {}
            if category == "refund":
                summary = {"refund": summary.get("refund"), "payment": summary.get("payment")}
            elif category == "payment":
                summary = {"payment": summary.get("payment"), "refund": summary.get("refund")}
            elif category == "shipping":
                summary = {"shipment": summary.get("shipment")}
            elif category == "return":
                summary = {"return": summary.get("return"), "refund": summary.get("refund")}
            else:
                summary = {"shipment": summary.get("shipment"), "refund": summary.get("refund"), "return": summary.get("return"), "payment": summary.get("payment")}
            records.extend(_record_evidence("transaction_database", "order_transactions", {"found": True, "data": summary}))

    elif route == "customer_database":
        if category == "order" or "order" in query or "purchase" in query:
            orders = get_customer_order_information(customer_id, session_id)
            if orders.get("found"):
                # Do not pass full shipping addresses or contact fields to Maker.
                visible = [{key: order.get(key) for key in ("order_id", "product_name", "quantity", "total_amount", "currency", "order_date", "order_status", "payment_status", "estimated_delivery", "tracking_number")} for order in orders["data"]]
                records.extend(_record_evidence("customer_order_database", "customer_orders", {"found": True, "data": visible}))
        else:
            customer = get_customer_information(customer_id, session_id)
            if customer.get("found"):
                requested_fields = []
                for word, field in (("email", "email"), ("phone", "phone"), ("address", "default_city"), ("city", "default_city"), ("state", "default_state"), ("name", "name"), ("membership", "membership_tier"), ("tier", "membership_tier")):
                    if word in query and field not in requested_fields:
                        requested_fields.append(field)
                if not requested_fields:
                    requested_fields = ["name", "membership_tier", "account_status", "preferred_language"]
                visible = {key: customer["data"].get(key) for key in ("customer_id", *requested_fields)}
                records.extend(_record_evidence("customer_database", "customer", {"found": True, "data": visible}))

    elif route == "account_database":
        if category == "order" or any(word in query for word in ("orders", "order history", "purchases")):
            orders = get_customer_order_information(customer_id, session_id)
            if orders.get("found"):
                visible = [{key: order.get(key) for key in ("order_id", "product_name", "quantity", "total_amount", "currency", "order_date", "order_status", "payment_status", "estimated_delivery", "tracking_number")} for order in orders["data"]]
                records.extend(_record_evidence("customer_order_database", "customer_orders", {"found": True, "data": visible}))
        if any(term in query for term in ("refund", "payment", "transaction", "return", "shipment", "tracking")):
            transactions = get_customer_transaction_information(customer_id, session_id)
            if transactions.get("found"):
                data = transactions["data"]
                requested_type = "refunds" if "refund" in query else ("payments" if "payment" in query else ("returns" if "return" in query else ("shipments" if any(word in query for word in ("shipment", "tracking", "delivery")) else None)))
                if requested_type:
                    data = {requested_type: data.get(requested_type, [])}
                records.extend(_record_evidence("transaction_database", "customer_transactions", {"found": True, "data": data}))
        if any(term in query for term in ("account", "profile", "membership", "tier", "email", "phone", "address", "my name")):
            customer = get_customer_information(customer_id, session_id)
            if customer.get("found"):
                requested_fields = []
                for word, field in (("email", "email"), ("phone", "phone"), ("address", "default_city"), ("city", "default_city"), ("state", "default_state"), ("name", "name"), ("membership", "membership_tier"), ("tier", "membership_tier")):
                    if word in query and field not in requested_fields:
                        requested_fields.append(field)
                if not requested_fields:
                    requested_fields = ["name", "membership_tier", "account_status", "preferred_language"]
                visible = {key: customer["data"].get(key) for key in ("customer_id", *requested_fields)}
                records.extend(_record_evidence("customer_database", "customer", {"found": True, "data": visible}))

    elif route == "product_database":
        result = get_product_information(state.get("user_query", ""))
        records.extend(_record_evidence("vericommerce_product_catalog", "products", result))

    elif route == "promotion_database":
        result = get_promotion_information()
        records.extend(_record_evidence("vericommerce_promotion_catalog", "promotions", result))

    elif route == "case_database":
        result = get_support_case_information(state.get("case_id"), session_id)
        if result.get("found"):
            data = result["data"]
            if isinstance(data, list):
                data = [{key: case.get(key) for key in ("case_id", "topic", "status", "priority", "created_at", "updated_at", "channel")} for case in data]
                evidence_type = "support_cases"
            else:
                data = {key: data.get(key) for key in ("case_id", "topic", "status", "priority", "created_at", "updated_at", "channel")}
                evidence_type = "support_case"
            records.extend(_record_evidence("customer_support_case_database", evidence_type, {"found": True, "data": data}))

    return {"account_evidence": records, "node_latency_ms": _timed(state, "account_data", started)}


def build_combined_evidence(state: VeriTrustState):
    return list(state.get("evidence", [])) + list(state.get("account_evidence", []))


def maker_node(state: VeriTrustState):
    started = perf_counter()
    evidence = build_combined_evidence(state)
    response = maker_agent(state.get("user_query", ""), evidence)
    return {"combined_evidence": evidence, "draft_response": response, "node_latency_ms": _timed(state, "maker", started)}


def claim_extraction_node(state: VeriTrustState):
    started = perf_counter()
    claims = extract_claims(state.get("draft_response", ""))
    return {"claims": claims, "node_latency_ms": _timed(state, "claim_extraction", started)}


def policy_check_node(state: VeriTrustState):
    started = perf_counter()
    evidence = state.get("combined_evidence") or build_combined_evidence(state)
    verification = verify_claims(state.get("claims", []), evidence)
    policy = check_policy_contradictions(state.get("draft_response", ""), evidence, verification)
    return {
        "claim_verification": verification,
        "policy_check": policy,
        "node_latency_ms": _timed(state, "verification", started),
    }


def judge_node(state: VeriTrustState):
    started = perf_counter()
    judgment = judge_agent(
        state.get("user_query", ""),
        state.get("draft_response", ""),
        state.get("combined_evidence") or build_combined_evidence(state),
        state.get("claim_verification"),
        state.get("policy_check"),
    )
    return {"judgment": judgment, "node_latency_ms": _timed(state, "judge", started)}


def correction_node(state: VeriTrustState):
    started = perf_counter()
    evidence = state.get("combined_evidence") or build_combined_evidence(state)
    corrected = corrector_agent(state.get("user_query", ""), state.get("draft_response", ""), evidence, state.get("policy_check", {}))
    return {"corrected_response": corrected, "correction_performed": True, "node_latency_ms": _timed(state, "correction", started)}


def corrected_claim_node(state: VeriTrustState):
    started = perf_counter()
    return {"final_claims": extract_claims(state.get("corrected_response", "")), "node_latency_ms": _timed(state, "final_claim_extraction", started)}


def corrected_policy_node(state: VeriTrustState):
    started = perf_counter()
    response = state.get("corrected_response", "")
    evidence = state.get("combined_evidence") or build_combined_evidence(state)
    verification = verify_claims(state.get("final_claims", []), evidence)
    policy = check_policy_contradictions(response, evidence, verification)
    return {"final_claim_verification": verification, "final_policy_check": policy, "node_latency_ms": _timed(state, "final_verification", started)}


def final_judge_node(state: VeriTrustState):
    started = perf_counter()
    verification = state.get("final_claim_verification", {})
    policy = state.get("final_policy_check", {})
    judgment = judge_agent(
        state.get("user_query", ""),
        state.get("corrected_response", ""),
        state.get("combined_evidence") or build_combined_evidence(state),
        verification,
        policy,
    )
    return {"final_judgment": judgment, "node_latency_ms": _timed(state, "final_judge", started)}


def approved_response_node(state: VeriTrustState):
    is_corrected = bool(state.get("correction_performed"))
    response = state.get("corrected_response") if is_corrected else state.get("draft_response")
    judgment = state.get("final_judgment") if is_corrected else state.get("judgment", {})
    return {
        "final_response": response or _REVIEW_REPLY,
        "decision": "CORRECT" if is_corrected else "APPROVE",
        "risk": "MEDIUM" if is_corrected else judgment.get("risk", "LOW"),
        "judgment": judgment,
    }


def review_response_node(state: VeriTrustState):
    return {"final_response": _REVIEW_REPLY, "decision": "REVIEW", "risk": "MEDIUM"}


def final_gate_node(state: VeriTrustState):
    judgment = state.get("final_judgment", {})
    if judgment.get("decision") == "BLOCK" or state.get("final_policy_check", {}).get("decision") == "BLOCK":
        return {"final_response": _SECURITY_REPLY, "decision": "BLOCK", "risk": "HIGH"}
    if judgment.get("decision") == "APPROVE" and state.get("final_policy_check", {}).get("decision") == "APPROVE" and state.get("final_claim_verification", {}).get("decision") == "APPROVE":
        return approved_response_node(state)
    return {"final_response": _REVIEW_REPLY, "decision": "REVIEW", "risk": "MEDIUM"}


def route_after_authentication(state: VeriTrustState):
    return "security_response" if state.get("security_blocked") else "retrieve"


def route_after_judge(state: VeriTrustState):
    decision = (state.get("judgment") or {}).get("decision", "REVIEW")
    if decision == "BLOCK":
        return "security_response"
    if decision == "CORRECT":
        return "correct"
    if decision == "REVIEW":
        return "review_response"
    return "approved_response"


def route_after_final_judge(state: VeriTrustState):
    decision = (state.get("final_judgment") or {}).get("decision", "REVIEW")
    if decision == "BLOCK":
        return "final_gate"
    return "final_gate"


def build_veritrust_graph():
    graph = StateGraph(VeriTrustState)
    for name, node in (
        ("query_router", query_router_node),
        ("account_router", account_router_node),
        ("authenticate", authentication_node),
        ("retrieve", retrieve_node),
        ("account_data", account_data_node),
        ("maker", maker_node),
        ("claim_extraction", claim_extraction_node),
        ("policy_check", policy_check_node),
        ("judge", judge_node),
        ("correct", correction_node),
        ("corrected_claims", corrected_claim_node),
        ("corrected_policy", corrected_policy_node),
        ("final_judge", final_judge_node),
        ("approved_response", approved_response_node),
        ("review_response", review_response_node),
        ("security_response", security_response_node),
        ("final_gate", final_gate_node),
    ):
        graph.add_node(name, node)

    graph.set_entry_point("query_router")
    graph.add_edge("query_router", "account_router")
    graph.add_edge("account_router", "authenticate")
    graph.add_conditional_edges("authenticate", route_after_authentication, {"retrieve": "retrieve", "security_response": "security_response"})
    graph.add_edge("retrieve", "account_data")
    graph.add_edge("account_data", "maker")
    graph.add_edge("maker", "claim_extraction")
    graph.add_edge("claim_extraction", "policy_check")
    graph.add_edge("policy_check", "judge")
    graph.add_conditional_edges("judge", route_after_judge, {"correct": "correct", "approved_response": "approved_response", "review_response": "review_response", "security_response": "security_response"})
    graph.add_edge("correct", "corrected_claims")
    graph.add_edge("corrected_claims", "corrected_policy")
    graph.add_edge("corrected_policy", "final_judge")
    graph.add_edge("final_judge", "final_gate")
    graph.add_edge("final_gate", END)
    graph.add_edge("approved_response", END)
    graph.add_edge("review_response", END)
    graph.add_edge("security_response", END)
    return graph.compile()


def invoke_veritrust(user_query: str, session_id: str | None = None, request_id: str | None = None):
    """Invoke the graph from API/service code and return audit-ready state."""
    graph = build_veritrust_graph()
    rid = request_id or str(uuid.uuid4())
    started = perf_counter()
    initial: VeriTrustState = {
        "request_id": rid,
        "session_id": session_id,
        "user_query": user_query,
        "node_latency_ms": {},
        "correction_performed": False,
    }
    result = graph.invoke(initial)
    result["request_id"] = rid
    result["latency_ms"] = round((perf_counter() - started) * 1000, 3)
    result["sources"] = [
        {key: item.get(key) for key in ("source", "document_id", "category", "version", "effective_date", "source_type", "distance", "similarity_score", "category_match", "type") if item.get(key) is not None}
        for item in result.get("evidence", []) + result.get("account_evidence", [])
    ]
    return result
