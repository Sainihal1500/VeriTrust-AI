"""Persistent SQLite audit trail and aggregate service metrics."""

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
from threading import RLock

from database.customer_data import CUSTOMERS
from database.transaction_data import PAYMENTS, REFUNDS, RETURNS, SHIPMENTS
from database.customer_data import ORDERS
from database.catalog_data import PRODUCTS, PROMOTIONS
from database.support_data import SUPPORT_CASES

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
AUDIT_DB = DATA_DIR / "veritrust_audit.sqlite3"
_lock = RLock()


def redact_sensitive_text(value: str | None) -> str:
    """Remove submitted credential values before any text is persisted."""
    text = value or ""
    text = re.sub(r"(?i)\b(?:otp|one[- ]time (?:password|code)|verification code|pin|cvv)\s*(?:is|:|=)?\s*\d{4,10}\b", "[REDACTED_CREDENTIAL]", text)
    text = re.sub(r"(?i)\bpassword\s*(?:is|:|=)\s*[^\s,;]+", "password [REDACTED_CREDENTIAL]", text)
    text = re.sub(r"(?i)\b(?:password|passcode)\s+[A-Za-z0-9!@#$%^&*_-]{8,}\b", "password [REDACTED_CREDENTIAL]", text)
    return text[:5000]


def _json(value):
    return json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))


def _redact_payload(value):
    if isinstance(value, dict):
        sensitive_keys = {"password", "otp", "one_time_password", "pin", "cvv", "secret", "credential", "authentication_code"}
        security_claim = str(value.get("type", "")).casefold() == "security"
        output = {}
        for key, item in value.items():
            normalized = str(key).casefold()
            if normalized in sensitive_keys or (security_claim and normalized == "value" and item is not None and item != "disclosure_requested"):
                output[key] = "[REDACTED_CREDENTIAL]"
            else:
                output[key] = _redact_payload(item)
        return output
    if isinstance(value, list):
        return [_redact_payload(item) for item in value]
    if isinstance(value, str):
        return redact_sensitive_text(value)
    return value


def _safe_json(value):
    return _json(_redact_payload(value))


def _connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(AUDIT_DB, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("""CREATE TABLE IF NOT EXISTS audit_events (
        request_id TEXT PRIMARY KEY,
        timestamp TEXT NOT NULL,
        session_id TEXT,
        customer_id TEXT,
        user_query TEXT NOT NULL,
        query_category TEXT,
        decision TEXT,
        risk TEXT,
        latency_ms REAL,
        retrieved_sources TEXT NOT NULL,
        account_sources TEXT NOT NULL,
        maker_response TEXT,
        claims TEXT NOT NULL,
        claim_verification TEXT NOT NULL,
        policy_check TEXT NOT NULL,
        judge_decision TEXT NOT NULL,
        corrected_response TEXT,
        final_response TEXT,
        security_result TEXT NOT NULL,
        node_latency_ms TEXT NOT NULL,
        request_type TEXT NOT NULL
    )""")
    connection.commit()
    return connection


def record_audit_event(event: dict):
    timestamp = event.get("timestamp") or datetime.now(timezone.utc).isoformat()
    retrieved_sources = event.get("retrieved_sources", [])
    account_sources = event.get("account_sources", [])
    values = (
        event["request_id"], timestamp, event.get("session_id"), event.get("customer_id"),
        redact_sensitive_text(event.get("user_query")), event.get("query_category"),
        event.get("decision"), event.get("risk"), float(event.get("latency_ms", 0) or 0),
        _json(retrieved_sources), _json(account_sources), redact_sensitive_text(event.get("maker_response")),
        _safe_json(event.get("claims", [])), _safe_json(event.get("claim_verification", {})),
        _safe_json(event.get("policy_check", {})), _safe_json(event.get("judge_decision", {})),
        redact_sensitive_text(event.get("corrected_response")), redact_sensitive_text(event.get("final_response")),
        _json(event.get("security_result", {})), _json(event.get("node_latency_ms", {})),
        event.get("request_type", "chat"),
    )
    with _lock, _connect() as connection:
        connection.execute("""INSERT OR REPLACE INTO audit_events (
            request_id,timestamp,session_id,customer_id,user_query,query_category,decision,risk,latency_ms,
            retrieved_sources,account_sources,maker_response,claims,claim_verification,policy_check,
            judge_decision,corrected_response,final_response,security_result,node_latency_ms,request_type
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", values)
        connection.commit()
    return get_audit_event(event["request_id"])


def _decode_row(row):
    if row is None:
        return None
    result = dict(row)
    for key in ("retrieved_sources", "account_sources", "claims", "claim_verification", "policy_check", "judge_decision", "security_result", "node_latency_ms"):
        try:
            result[key] = json.loads(result[key])
        except (TypeError, json.JSONDecodeError):
            result[key] = [] if key in {"retrieved_sources", "account_sources", "claims"} else {}
    return result


def get_audit_event(request_id: str):
    with _lock, _connect() as connection:
        row = connection.execute("SELECT * FROM audit_events WHERE request_id = ?", (request_id,)).fetchone()
    return _decode_row(row)


def list_recent_audit(session_id: str | None = None, limit: int = 20):
    with _lock, _connect() as connection:
        if session_id:
            rows = connection.execute("SELECT * FROM audit_events WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?", (session_id, max(1, min(limit, 100)))).fetchall()
        else:
            rows = connection.execute("SELECT * FROM audit_events ORDER BY timestamp DESC LIMIT ?", (max(1, min(limit, 100)),)).fetchall()
    return [_decode_row(row) for row in rows]


def get_metrics():
    with _lock, _connect() as connection:
        rows = connection.execute("SELECT decision,risk,latency_ms,claims,claim_verification,policy_check,node_latency_ms FROM audit_events").fetchall()
    metrics = {
        "total_requests": len(rows), "approved": 0, "corrected": 0, "blocked": 0, "reviewed": 0,
        "high_risk": 0, "low_risk": 0, "unsupported_claims": 0, "policy_contradictions": 0,
        "average_latency_ms": 0.0, "retrieval_latency_ms": 0.0, "maker_latency_ms": 0.0,
        "judge_latency_ms": 0.0, "correction_latency_ms": 0.0,
    }
    latency_sums = {"retrieval": 0.0, "maker": 0.0, "judge": 0.0, "correction": 0.0}
    latency_counts = {key: 0 for key in latency_sums}
    total_latency = 0.0
    for row in rows:
        decision, risk = (row["decision"] or "").upper(), (row["risk"] or "").upper()
        metric_key = {"APPROVE": "approved", "CORRECT": "corrected", "BLOCK": "blocked", "REVIEW": "reviewed"}.get(decision)
        if metric_key:
            metrics[metric_key] += 1
        if risk == "HIGH":
            metrics["high_risk"] += 1
        elif risk == "LOW":
            metrics["low_risk"] += 1
        total_latency += float(row["latency_ms"] or 0)
        try:
            verification = json.loads(row["claim_verification"] or "{}")
            policy = json.loads(row["policy_check"] or "{}")
            verification_items = [verification[key] for key in ("initial", "final") if isinstance(verification.get(key), dict)] or [verification]
            policy_items = [policy[key] for key in ("initial", "final") if isinstance(policy.get(key), dict)] or [policy]
            for item in verification_items:
                metrics["unsupported_claims"] += len(item.get("unsupported_claims", []))
            for item in policy_items:
                metrics["policy_contradictions"] += len(item.get("contradicted_claims", []))
            timings = json.loads(row["node_latency_ms"] or "{}")
            for key in latency_sums:
                value = timings.get(key)
                if key == "judge" and (timings.get("final_judge") is not None):
                    value = float(value or 0) + float(timings["final_judge"] or 0)
                if value is not None:
                    latency_sums[key] += float(value)
                    latency_counts[key] += 1
        except (TypeError, json.JSONDecodeError, ValueError):
            continue
    if rows:
        metrics["average_latency_ms"] = round(total_latency / len(rows), 2)
    for key in latency_sums:
        metrics[f"{key}_latency_ms"] = round(latency_sums[key] / latency_counts[key], 2) if latency_counts[key] else 0.0
    metrics["average_latency"] = metrics["average_latency_ms"]
    for key in latency_sums:
        metrics[f"{key}_latency"] = metrics[f"{key}_latency_ms"]
    metrics["dataset"] = {
        "customers": len(CUSTOMERS), "orders": len(ORDERS), "payments": len(PAYMENTS),
        "refunds": len(REFUNDS), "returns": len(RETURNS), "shipments": len(SHIPMENTS),
        "products": len(PRODUCTS), "promotions": len(PROMOTIONS), "support_cases": len(SUPPORT_CASES),
    }
    return metrics
