"""One-pass deterministic validation for the VeriTrust demo platform.

Run from the project root with ``python backend/app/validate_system.py``.
Knowledge ingestion is attempted by default; pass ``--skip-ingest`` only when
checking code in an environment where the local embedding model is unavailable.
"""

import argparse
from collections import Counter
import importlib
import json
from pathlib import Path
import tempfile
import traceback
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[2]
APP_DIR = Path(__file__).resolve().parent


class Validation:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.warnings = []

    def check(self, name, callback):
        try:
            result = callback()
            if result is False:
                raise AssertionError("condition returned false")
            self.passed.append(name)
            print(f"PASS {name}")
            return result
        except Exception as exc:
            self.failed.append({"name": name, "error": f"{type(exc).__name__}: {exc}"})
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
            return None


def _imports(v):
    modules = (
        "agents.account_router", "agents.claim_extractor", "agents.claim_verifier",
        "agents.corrector", "agents.judge", "agents.maker", "agents.policy_checker",
        "agents.query_router", "database.account_service", "database.catalog_data",
        "database.customer_data", "database.transaction_data", "database.transaction_service",
        "database.support_data",
        "security.access_control", "security.session", "rag.ingest", "rag.retriever",
        "workflows.veritrust_graph", "audit", "api.main", "demo.scenarios",
    )
    for module in modules:
        importlib.import_module(module)
    return modules


def _data_integrity():
    from database.catalog_data import PRODUCTS_BY_ID
    from database.customer_data import CUSTOMERS, ORDERS
    from database.transaction_data import PAYMENTS, REFUNDS, RETURNS, SHIPMENTS
    from database.support_data import SUPPORT_CASES

    assert len(CUSTOMERS) >= 100
    assert len(ORDERS) >= 300
    assert len(PAYMENTS) >= 300
    assert len(REFUNDS) >= 100
    assert len(RETURNS) >= 100
    assert len(SHIPMENTS) >= 300
    assert len(PRODUCTS_BY_ID) >= 12
    assert len(SUPPORT_CASES) >= 10
    for order in ORDERS.values():
        assert order["customer_id"] in CUSTOMERS, order["order_id"]
        assert order["product_id"] in PRODUCTS_BY_ID, order["order_id"]
        assert order["total_amount"] == order["unit_price"] * order["quantity"], order["order_id"]
        assert order["shipment_id"] in SHIPMENTS, order["order_id"]
    for records in (PAYMENTS, REFUNDS, RETURNS, SHIPMENTS):
        for record in records.values():
            order = ORDERS[record["order_id"]]
            assert record["customer_id"] == order["customer_id"], record
    for payment in PAYMENTS.values():
        assert payment["amount"] == ORDERS[payment["order_id"]]["total_amount"]
    for case in SUPPORT_CASES.values():
        assert case["customer_id"] in CUSTOMERS
        assert case["order_id"] in ORDERS
        assert ORDERS[case["order_id"]]["customer_id"] == case["customer_id"]
    for customer in CUSTOMERS.values():
        assert all(key in customer for key in ("customer_id", "name", "email", "phone", "membership_tier", "account_status", "created_at", "default_city", "default_state", "preferred_language"))
        assert customer["email"].endswith("@demo.vericommerce.example")
    return {"customers": len(CUSTOMERS), "orders": len(ORDERS), "payments": len(PAYMENTS), "refunds": len(REFUNDS), "returns": len(RETURNS), "shipments": len(SHIPMENTS), "products": len(PRODUCTS_BY_ID), "support_cases": len(SUPPORT_CASES)}


def _security_checks():
    from database.account_service import get_customer_information, get_order_information, get_order_transaction_information
    from database.account_service import get_support_case_information
    from database.support_data import SUPPORT_CASES
    from security.access_control import verify_customer_access, verify_order_access
    from database.customer_data import get_order

    assert verify_customer_access("SESSION-1001", "CUST-1001")["allowed"]
    assert not verify_customer_access("SESSION-1001", "CUST-1003")["allowed"]
    assert verify_order_access("SESSION-1001", get_order("ORD-10001"))["allowed"]
    assert not verify_order_access("SESSION-1001", get_order("ORD-10003"))["allowed"]
    assert not verify_order_access("NO-SUCH-SESSION", get_order("ORD-10001"))["allowed"]
    denied = get_order_information("ORD-10003", "SESSION-1001")
    assert denied["authorized"] is False and "data" not in denied
    assert get_order_information("ORD-10001", "SESSION-1001")["authorized"] is True
    assert get_order_transaction_information("ORD-10003", "SESSION-1001")["authorized"] is False
    assert get_customer_information("CUST-1003", "SESSION-1001")["authorized"] is False
    case = next(iter(SUPPORT_CASES.values()))
    assert get_support_case_information(case["case_id"], f"SESSION-{int(case['customer_id'][-4:])}")["authorized"] is True
    assert get_support_case_information(case["case_id"], "SESSION-1001")["authorized"] is (case["customer_id"] == "CUST-1001")
    own_case = get_support_case_information("CASE-00100", "SESSION-1001")
    other_case = get_support_case_information("CASE-00001", "SESSION-1001")
    assert own_case["authorized"] is True
    assert other_case["authorized"] is False and "data" not in other_case
    return True


def _routing_checks():
    from agents.query_router import route_query
    from agents.account_router import route_account_query
    cases = {
        "Where is my package?": "shipping",
        "My money hasn't come back": "refund",
        "Can I send this laptop back?": "return",
        "My UPI payment failed": "payment",
        "Is this laptop covered?": "warranty",
        "I forgot my password": "security",
        "Delete my personal data": "privacy",
        "Does this monitor support HDMI?": "product",
        "Can I cancel my order?": "cancellation",
        "Where is my order ORD-10001?": "shipping",
    }
    for query, expected in cases.items():
        actual = route_query(query)
        assert actual == expected, f"{query}: expected {expected}, got {actual}"
    assert route_account_query("Where is my order ORD-10001?", "shipping")["route"] == "order_database"
    assert route_account_query("What are your refund rules?", "refund")["route"] == "knowledge_base"
    assert route_account_query("Does this monitor support HDMI?", "product")["route"] == "product_database"
    return cases


def _claim_checks():
    from agents.claim_extractor import rule_based_claims
    from agents.claim_verifier import verify_claims
    from agents.policy_checker import check_policy_contradictions

    bad_refund = rule_based_claims("Refunds are available within 60 calendar days of purchase.")
    assert any(claim["type"] == "time_limit" and claim["value"].startswith("60") for claim in bad_refund)
    delivery = rule_based_claims("Your delivery is guaranteed to arrive within 3 days.")
    assert any(claim["type"] == "shipping_guarantee" for claim in delivery)
    money = rule_based_claims("Your refund of INR 3,998 will be completed on 2026-10-03.")
    assert any(claim["type"] == "money" and claim["value"] == "3998" for claim in money)
    assert any(claim["type"] == "date" for claim in money)
    assert any(claim["type"] == "tracking_number" for claim in rule_based_claims("Track it with TRK-IND-10001."))
    assert not any(claim["type"] == "security" for claim in rule_based_claims("Never share your OTP with anyone."))
    unsafe = rule_based_claims("Please share your OTP with support.")
    assert any(claim["type"] == "security" for claim in unsafe)

    evidence = [{"text": "Customers may request a refund within 30 calendar days of purchase. Approved refunds are processed within 5-7 business days after approval. Delivery dates are estimates and are not guaranteed. Never share passwords or one-time codes with support."}]
    assert verify_claims(bad_refund, evidence)["contradicted_claims"]
    assert check_policy_contradictions("Refunds are available within 60 days.", evidence)["decision"] == "CORRECT"
    assert check_policy_contradictions("Your delivery is guaranteed to arrive within 3 days.", evidence)["decision"] == "CORRECT"
    assert check_policy_contradictions("You can cancel your order even after it has shipped.", [{"text": "Orders may be cancelled before shipment. Once an order has shipped, cancellation is normally unavailable."}])["decision"] == "CORRECT"
    assert check_policy_contradictions("Please share your OTP with the support agent.", evidence)["decision"] == "BLOCK"
    assert check_policy_contradictions("Never share your OTP with support.", evidence)["decision"] == "APPROVE"
    assert check_policy_contradictions("You are guaranteed to receive a refund today.", [{"text": "Refunds are subject to eligibility approval."}])["decision"] == "CORRECT"
    return True


def _graph_checks():
    from unittest.mock import patch
    import workflows.veritrust_graph as workflow
    from agents.claim_extractor import rule_based_claims

    no_retrieval = Mock(return_value=[])
    no_maker = Mock(return_value="Order ORD-10003 is delivered.")
    with patch.object(workflow, "retrieve_evidence", no_retrieval), patch.object(workflow, "maker_agent", no_maker):
        blocked = workflow.invoke_veritrust("Where is my order ORD-10003?", "SESSION-1001")
    assert blocked["decision"] == "BLOCK"
    assert not no_retrieval.called and not no_maker.called
    assert "CUST-1003" not in blocked["final_response"]

    with patch.object(workflow, "retrieve_evidence", no_retrieval), patch.object(workflow, "maker_agent", no_maker):
        blocked_case = workflow.invoke_veritrust("What is the status of support case CASE-00001?", "SESSION-1001")
        authorized_case = workflow.invoke_veritrust("What is the status of my support case CASE-00100?", "SESSION-1001")
    assert blocked_case["decision"] == "BLOCK" and not blocked_case.get("account_evidence", [])
    assert authorized_case["security_result"]["authorized"] is True
    assert any(item.get("type") == "support_case" for item in authorized_case["account_evidence"])

    policy = [{"text": "Customers may request a refund within 30 calendar days of purchase. Requests after that period need supervisor review." , "source": "refund_policy.txt", "document_id": "REFUND-001", "category": "refund", "version": "1.0", "effective_date": "2026-01-01", "source_type": "official_internal_policy", "distance": 0.1, "category_match": True}]

    def fake_judge(query, response, evidence, claim_verification=None, policy_check=None):
        if (policy_check or {}).get("decision") == "BLOCK":
            return {"decision": "BLOCK", "risk": "HIGH", "reason": "Security policy block.", "contradicted_claims": []}
        if (policy_check or {}).get("decision") == "REVIEW" or (claim_verification or {}).get("decision") == "REVIEW":
            return {"decision": "REVIEW", "risk": "MEDIUM", "reason": "Insufficient evidence.", "contradicted_claims": []}
        if (policy_check or {}).get("decision") == "CORRECT" or (claim_verification or {}).get("decision") == "CORRECT":
            return {"decision": "CORRECT", "risk": "HIGH", "reason": "Claim needs correction.", "contradicted_claims": []}
        return {"decision": "APPROVE", "risk": "LOW", "reason": "Evidence verified.", "contradicted_claims": []}

    with patch.object(workflow, "retrieve_evidence", return_value=[]), \
         patch.object(workflow, "maker_agent", return_value="Order ORD-10001 is shipped."), \
         patch.object(workflow, "extract_claims", side_effect=rule_based_claims), \
         patch.object(workflow, "judge_agent", side_effect=fake_judge):
        valid = workflow.invoke_veritrust("What is the status of ORD-10001?", "SESSION-1001")
    assert valid["decision"] == "APPROVE", valid.get("judgment")
    assert valid["final_response"] == "Order ORD-10001 is shipped."

    def correct_response(*args, **kwargs):
        return "Refund requests may be made within 30 calendar days of purchase."

    with patch.object(workflow, "retrieve_evidence", return_value=policy), \
         patch.object(workflow, "maker_agent", return_value="Refunds are available within 60 days of purchase."), \
         patch.object(workflow, "extract_claims", side_effect=rule_based_claims), \
         patch.object(workflow, "corrector_agent", side_effect=correct_response), \
         patch.object(workflow, "judge_agent", side_effect=fake_judge):
        corrected = workflow.invoke_veritrust("Can I get a refund?", None)
    assert corrected["decision"] == "CORRECT", corrected
    assert corrected["final_judgment"]["decision"] == "APPROVE", corrected.get("final_judgment")
    assert corrected["final_claim_verification"]["decision"] == "APPROVE"
    assert "60 days" not in corrected["final_response"]

    from demo.scenarios import DEMO_SCENARIOS
    from agents.maker import _fallback
    scenario_evidence = {
        "refund": [{"text": "Customers may request a refund within 30 calendar days of purchase. Refund requests after 30 days are not eligible for a standard refund. Approved refunds are processed within 5-7 business days after approval. Exceptions require eligibility review and supervisor approval.", "source": "refund_policy.txt", "document_id": "REFUND-001", "category": "refund", "version": "1.0", "effective_date": "2026-01-01", "source_type": "official_internal_policy", "distance": 0.1, "category_match": True}],
        "shipping": [{"text": "Standard delivery generally takes 3-7 business days after shipment. Delivery times are estimates and are not guaranteed.", "source": "shipping_policy.txt", "document_id": "SHIPPING-001", "category": "shipping", "version": "1.0", "effective_date": "2026-01-01", "source_type": "official_internal_policy", "distance": 0.1, "category_match": True}],
        "security": [{"text": "Customers must never share passwords or one-time authentication codes with support.", "source": "otp_password_policy.txt", "document_id": "SECURITY-CREDENTIALS-001", "category": "security", "version": "1.0", "effective_date": "2026-01-01", "source_type": "official_internal_policy", "distance": 0.1, "category_match": True}],
    }
    by_message = {scenario["message"]: scenario for scenario in DEMO_SCENARIOS}

    def scenario_maker(query, evidence):
        scenario = by_message[query]
        if scenario.get("maker_response"):
            return scenario["maker_response"]
        if scenario["category"] == "security":
            return "Never share your OTP, password, or PIN with support. Use the official account recovery flow."
        return "I can’t verify all requested details from the available record. VeriCommerce support can review the request."

    def scenario_claims(response):
        if response.startswith("Every customer receives a free laptop"):
            return [{"claim": response, "type": "promotion", "subject": "promotion", "value": "free laptop", "source": "rule"}]
        return rule_based_claims(response)

    with patch.object(workflow, "retrieve_evidence", side_effect=lambda query, category, n_results=6: scenario_evidence.get(category, [])), \
         patch.object(workflow, "maker_agent", side_effect=scenario_maker), \
         patch.object(workflow, "extract_claims", side_effect=scenario_claims), \
         patch.object(workflow, "corrector_agent", side_effect=lambda query, draft, evidence, findings: _fallback(query, evidence)), \
         patch.object(workflow, "judge_agent", side_effect=fake_judge):
        for scenario in DEMO_SCENARIOS:
            result = workflow.invoke_veritrust(scenario["message"], scenario["session_id"])
            assert result["query_category"] == scenario["category"], (scenario["id"], result.get("query_category"))
            assert result["decision"] == scenario["expected"], (scenario["id"], result.get("decision"), result.get("policy_check"), result.get("final_policy_check"))
            if scenario["id"] == "corrected_response":
                assert result.get("final_judgment", {}).get("decision") == "APPROVE"
    return True


def _retrieval_checks():
    import chromadb
    from rag.retriever import CHROMA_PATH, KNOWLEDGE_BASE, retrieve_evidence
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection = client.get_collection("veritrust_knowledge")
    documents = sorted(KNOWLEDGE_BASE.rglob("*.txt"))
    records = collection.get(limit=min(collection.count(), 30), include=["metadatas", "documents"])
    assert collection.count() >= 200
    assert len(documents) >= 25
    assert records["documents"] and all(item for item in records["metadatas"])
    for metadata in records["metadatas"]:
        assert all(metadata.get(key) for key in ("document_id", "version", "effective_date", "source_type", "category"))
    evidence = retrieve_evidence("What is the refund request period?", "refund", n_results=4)
    assert evidence
    assert all("distance" in item and item.get("document_id") for item in evidence)
    assert any(item.get("category_match") for item in evidence)
    return {"policy_documents": len(documents), "chroma_chunks": collection.count(), "retrieval_sources": len(evidence)}


def _api_checks():
    from fastapi.testclient import TestClient
    import api.main as api
    import audit
    from agents.claim_extractor import rule_based_claims

    with tempfile.TemporaryDirectory(prefix="veritrust-validation-") as directory:
        audit.AUDIT_DB = Path(directory) / "audit.sqlite3"

        def context(message, session_id=None, request_id=None):
            return {
                "request_id": request_id or "validation-request", "authenticated_customer_id": "CUST-1001" if session_id == "SESSION-1001" else None,
                "decision": "APPROVE", "risk": "LOW", "query_category": "refund", "draft_response": "Refunds may be requested within 30 days.",
                "final_response": "Refund requests may be made within 30 calendar days of purchase.", "sources": [{"source": "refund_policy.txt", "document_id": "REFUND-001", "category": "refund", "version": "1.0", "effective_date": "2026-01-01", "source_type": "official_internal_policy", "distance": 0.1}],
                "evidence": [{"text": "Customers may request a refund within 30 calendar days of purchase."}], "account_evidence": [],
                "security_result": {"status": "PUBLIC", "authorized": True}, "node_latency_ms": {"retrieval": 3, "maker": 5, "judge": 2, "correction": 0}, "latency_ms": 12,
                "claims": [], "claim_verification": {"decision": "APPROVE", "unsupported_claims": [], "contradicted_claims": []}, "policy_check": {"decision": "APPROVE", "contradicted_claims": []}, "judgment": {"decision": "APPROVE", "risk": "LOW", "reason": "Verified."},
            }

        def fake_judge(query, response, evidence, claim_verification=None, policy_check=None):
            if (policy_check or {}).get("decision") in {"BLOCK", "CORRECT"}:
                return {"decision": policy_check["decision"], "risk": "HIGH", "reason": "Deterministic validation finding.", "contradicted_claims": policy_check.get("contradicted_claims", [])}
            return {"decision": "APPROVE", "risk": "LOW", "reason": "Verified against evidence.", "contradicted_claims": []}

        with patch.object(api, "invoke_veritrust", side_effect=context), \
             patch.object(api, "extract_claims", side_effect=rule_based_claims), \
             patch.object(api, "judge_agent", side_effect=fake_judge):
            client = TestClient(api.app)
            assert client.get("/health").status_code == 200
            chat = client.post("/chat", json={"session_id": "SESSION-1001", "message": "What is the refund period?"})
            assert chat.status_code == 200 and chat.json()["decision"] == "APPROVE"
            request_id = chat.json()["request_id"]
            own_audit = client.get(f"/audit/{request_id}", params={"session_id": "SESSION-1001"})
            assert own_audit.status_code == 200
            assert client.get(f"/audit/{request_id}", params={"session_id": "SESSION-1002"}).status_code == 404
            assert client.get("/order/ORD-10003", params={"session_id": "SESSION-1001"}).status_code == 404
            assert client.get("/customer/CUST-1003/orders", params={"session_id": "SESSION-1001"}).status_code == 404
            verified = client.post("/verify", json={"session_id": "SESSION-1001", "message": "Can I get a refund?", "response": "Refunds are available within 60 days."})
            assert verified.status_code == 200 and verified.json()["decision"] == "CORRECT", verified.json()
            metrics = client.get("/metrics").json()
            assert metrics["total_requests"] == 2 and metrics["approved"] == 1 and metrics["corrected"] == 1
            assert client.get("/audit/recent", params={"session_id": "SESSION-1001"}).status_code == 200
        return True


def _demo_catalog_checks():
    from demo.scenarios import DEMO_SCENARIOS
    from agents.query_router import route_query
    from agents.policy_checker import check_policy_contradictions
    from agents.judge import judge_agent

    assert len(DEMO_SCENARIOS) == 18
    ids = [scenario["id"] for scenario in DEMO_SCENARIOS]
    assert len(ids) == len(set(ids))
    for scenario in DEMO_SCENARIOS[:11]:
        assert route_query(scenario["message"]) == scenario["category"], scenario
    checks = {"hallucinated_refund_period": check_policy_contradictions(DEMO_SCENARIOS[11]["maker_response"], [{"text": "Refunds are available within 30 calendar days."}]),
              "hallucinated_delivery_guarantee": check_policy_contradictions(DEMO_SCENARIOS[12]["maker_response"], [{"text": "Delivery times are estimates and may be delayed."}]),
              "incorrect_refund_promise": check_policy_contradictions(DEMO_SCENARIOS[13]["maker_response"], [{"text": "Refunds are subject to eligibility approval."}]),
              "blocked_security_case": check_policy_contradictions(DEMO_SCENARIOS[17]["maker_response"], [])}
    assert checks["hallucinated_refund_period"]["decision"] == "CORRECT"
    assert checks["hallucinated_delivery_guarantee"]["decision"] == "CORRECT"
    assert checks["incorrect_refund_promise"]["decision"] == "CORRECT"
    assert checks["blocked_security_case"]["decision"] == "BLOCK"
    review = judge_agent("question", "The specialist approved it.", [], {"decision": "REVIEW"}, {"decision": "REVIEW"})
    assert review["decision"] == "REVIEW"
    return {"scenarios": len(DEMO_SCENARIOS), "special_checks": list(checks)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-ingest", action="store_true", help="Do not rebuild Chroma before validation")
    args = parser.parse_args()
    if str(APP_DIR) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(APP_DIR))
    validation = Validation()

    if not args.skip_ingest:
        def ingest():
            from rag.ingest import ingest_documents
            result = ingest_documents()
            assert result["collection_count"] == result["chunks"]
            return result
        validation.check("policy ingestion", ingest)

    validation.check("module import checks", lambda: _imports(validation))
    data = validation.check("dataset consistency and volume", _data_integrity)
    validation.check("security and ownership authorization", _security_checks)
    validation.check("query and account routing", _routing_checks)
    validation.check("claim extraction, verification, and policy checks", _claim_checks)
    validation.check("graph authorization and final correction flow", _graph_checks)
    retrieval = validation.check("policy metadata and Chroma retrieval", _retrieval_checks)
    validation.check("FastAPI authorization, audit, metrics, and verify", _api_checks)
    demos = validation.check("18 deterministic demo scenarios", _demo_catalog_checks)

    summary = {"passed": len(validation.passed), "failed": validation.failed, "dataset": data, "knowledge_base": retrieval, "demo_scenarios": demos}
    print("\nVALIDATION SUMMARY")
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    if validation.failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
