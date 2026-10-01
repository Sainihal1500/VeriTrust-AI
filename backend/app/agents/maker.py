"""Evidence-only customer-facing Maker agent with deterministic safe fallbacks."""

import json
import os
import re

from langchain_ollama import ChatOllama
from agents.llm_utils import ollama_available, strip_internal_reasoning

llm = ChatOllama(model=os.getenv("VERITRUST_CHAT_MODEL", "qwen3.5:latest"), temperature=0.1, num_predict=384, base_url=os.getenv("OLLAMA_BASE_URL") or None, client_kwargs={"timeout": 35})


def _account_records(evidence: list[dict]):
    records = []
    for item in evidence or []:
        data = item.get("structured_data")
        if data is None:
            continue
        records.append((str(item.get("type", "")), data))
    return records


def _unwrap(data):
    if isinstance(data, dict) and "found" in data:
        return data.get("data") if data.get("found") else None
    return data


def _account_fallback(user_query: str, evidence: list[dict]):
    query = user_query.casefold()
    order = None
    transactions = None
    customer = None
    orders = None
    for record_type, raw in _account_records(evidence):
        value = _unwrap(raw)
        if record_type == "order":
            order = value
        elif record_type in {"order_transactions", "customer_transactions"}:
            transactions = value
        elif record_type == "customer":
            customer = value
        elif record_type == "customer_orders":
            orders = value

    if order:
        order_id = order.get("order_id", "your order")
        if any(term in query for term in ("refund", "money back")) and transactions:
            refund = transactions.get("refund")
            if refund:
                return f"Refund for {order_id}: {refund.get('status', 'status unavailable')}. Amount: INR {refund.get('amount', 'unavailable')}. Estimated completion: {refund.get('estimated_completion') or 'not available in the record'}."
            return f"I don’t see a refund record for {order_id}. The order record shows its current status as {order.get('order_status', order.get('status', 'unavailable'))}."
        if any(term in query for term in ("payment", "charged", "upi", "card")) and transactions:
            payment = transactions.get("payment")
            if payment:
                return f"Payment for {order_id} is {payment.get('status', 'unavailable')} for INR {payment.get('amount', 'unavailable')} using {payment.get('payment_method', payment.get('method', 'a method not listed'))}."
        if any(term in query for term in ("track", "ship", "delivery", "package", "arrive", "where is", "where's")) and transactions:
            shipment = transactions.get("shipment")
            if shipment:
                details = f"Shipment for {order_id} is {shipment.get('status', 'unavailable')}"
                if shipment.get("tracking_number"):
                    details += f" (tracking {shipment['tracking_number']})"
                if shipment.get("estimated_delivery"):
                    details += f". Current estimated delivery: {shipment['estimated_delivery']}"
                return details + ". Delivery dates are estimates."
        status = order.get("order_status", order.get("status", "unavailable"))
        response = f"Order {order_id} for {order.get('product_name', order.get('product', 'the listed item'))} is {status}."
        if order.get("estimated_delivery"):
            response += f" Estimated delivery: {order['estimated_delivery']} (estimate)."
        return response

    if customer and any(term in query for term in ("account", "profile", "name", "email", "phone")):
        if "email" in query and customer.get("email"):
            return f"The email on your account is {customer['email']}."
        if "phone" in query and customer.get("phone"):
            return f"The phone number on your account is {customer['phone']}."
        if "name" in query and customer.get("name"):
            return f"The name on your account is {customer['name']}."
        if any(term in query for term in ("address", "city", "state")) and (customer.get("default_city") or customer.get("default_state")):
            return f"Your account’s default delivery location is {customer.get('default_city', 'not listed')}, {customer.get('default_state', 'not listed')}."
        return f"Your VeriCommerce account is {customer.get('account_status', 'active')} and your membership tier is {customer.get('membership_tier', 'standard')}."
    if orders is not None:
        if not orders:
            return "There are no orders listed for this account."
        return f"I found {len(orders)} orders on this account. Share an order ID if you want details about one order."

    for record_type, raw in _account_records(evidence):
        value = _unwrap(raw)
        if record_type == "customer_transactions" and isinstance(value, dict):
            for term, collection_name, label in (("refund", "refunds", "refund"), ("payment", "payments", "payment"), ("return", "returns", "return"), ("shipment", "shipments", "shipment"), ("tracking", "shipments", "shipment"), ("delivery", "shipments", "shipment")):
                records = value.get(collection_name)
                if term in query and isinstance(records, list):
                    if not records:
                        return f"There is no {label} record available for this account."
                    record = next((item for item in records if item.get("status") in {"failed", "processing", "pending", "in_transit", "out_for_delivery"}), records[0])
                    if label == "refund":
                        return f"Refund for {record.get('order_id', 'the listed order')} is {record.get('status', 'unavailable')} for INR {record.get('amount', 'unavailable')}. Estimated completion: {record.get('estimated_completion') or 'not available in the record'}."
                    if label == "payment":
                        return f"Payment for {record.get('order_id', 'the listed order')} is {record.get('status', 'unavailable')} for INR {record.get('amount', 'unavailable')} using {record.get('payment_method', record.get('method', 'a method not listed'))}."
                    if label == "shipment":
                        return f"Shipment for {record.get('order_id', 'the listed order')} is {record.get('status', 'unavailable')}. Tracking: {record.get('tracking_number') or 'not available'}. Estimated delivery: {record.get('estimated_delivery') or 'not available'}."
                    return f"Return for {record.get('order_id', 'the listed order')} is {record.get('status', 'unavailable')}."
        if record_type == "support_case" and isinstance(value, dict):
            return f"Support case {value.get('case_id', 'on your account')} about {value.get('topic', 'your request')} is {value.get('status', 'unavailable')}. Priority: {value.get('priority', 'not listed')}."
        if record_type == "support_cases" and isinstance(value, list):
            if not value:
                return "There are no support cases listed for this account."
            case = max(value, key=lambda item: item.get("created_at", ""))
            return f"Your latest support case {case.get('case_id')} about {case.get('topic', 'your request')} is {case.get('status', 'unavailable')}."
        if record_type == "products" and isinstance(value, list) and value:
            named = [product for product in value if product.get("name", "").casefold() in query]
            if len(value) > 1 and not named and any(term in query for term in ("laptop", "phone", "tablet", "monitor", "headphone", "camera", "router", "warranty", "covered")):
                if any(term in query for term in ("hdmi", "usb", "port", "connect", "compatible")):
                    port = next((token for token in ("hdmi", "usb-c", "usb-a", "displayport", "bluetooth") if token in query), None)
                    compatible = [product["name"] for product in value if port and port.casefold() in json.dumps(product.get("specifications", {}), ensure_ascii=False).casefold()]
                    if compatible:
                        return f"The catalog lists {port.upper()} connectivity for: {', '.join(compatible)}. Check the product specification for the exact model."
                    return "I can’t confirm that connection for the listed products. Share the exact model name and I can check its specifications."
                if any(term in query for term in ("warranty", "covered")):
                    return "Warranty periods and coverage depend on the specific product and issue. Share the exact model name so I can check its catalog warranty period; coverage still depends on the applicable warranty terms."
            product = named[0] if named else value[0]
            if any(term in query for term in ("hdmi", "usb", "port", "connect", "compatible")):
                return f"{product['name']} compatibility: {product.get('compatibility', 'not listed')}. Ports and specifications: {json.dumps(product.get('specifications', {}), ensure_ascii=False)}"
            if any(term in query for term in ("warranty", "covered")):
                return f"The catalog lists a {product.get('warranty_period', 'not listed')} warranty period for {product['name']}. That period does not by itself confirm coverage for a specific issue; applicable warranty terms must be checked."
            return f"{product['name']} is listed at INR {product.get('price', 'unavailable')} with {product.get('stock', 'unavailable')} units in demo stock. Warranty listed: {product.get('warranty_period', 'not listed')}. {product.get('description', '')}"
        if record_type == "promotions" and isinstance(value, list) and value:
            active = [item for item in value if item.get("status") == "active"]
            if active:
                promotion = active[0]
                return f"{promotion['name']} is listed as active through {promotion['valid_until']}: {promotion['discount']}. Terms: {promotion['terms']}"
    return None


def _policy_fallback(user_query: str, evidence: list[dict]):
    terms = [term for term in re.findall(r"[a-z0-9]+", user_query.casefold()) if len(term) > 3]
    candidates = []
    for item in evidence or []:
        if item.get("source_type") == "trusted_structured_database":
            continue
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", str(item.get("text", ""))):
            sentence = re.sub(r"\s+", " ", sentence).strip(" -\t")
            if len(sentence) < 35 or sentence.lower().startswith(("document id:", "version:", "effective date:")):
                continue
            score = sum(term in sentence.casefold() for term in terms)
            if score:
                candidates.append((score, sentence, item.get("source", "company policy")))
    if candidates:
        _, sentence, source = max(candidates, key=lambda row: row[0])
        return f"{sentence[:420]} [Source: {source}]"
    return "I don’t have enough verified information to answer that. I can ask customer support to review it."


def _fallback(user_query: str, evidence: list[dict]):
    account = _account_fallback(user_query, evidence)
    return account or _policy_fallback(user_query, evidence)


def maker_agent(user_query: str, evidence: list | None = None) -> str:
    """Draft a concise response using only trusted evidence supplied by the graph."""
    evidence = evidence or []
    if not evidence:
        return "I don’t have enough verified information to answer that. Please contact VeriCommerce support for a review."
    evidence_blocks = []
    for item in evidence:
        body = item.get("text", "")
        if item.get("structured_data") is not None:
            body = json.dumps(item["structured_data"], ensure_ascii=False, default=str)
        evidence_blocks.append(
            f"SOURCE: {item.get('source', 'trusted source')} | DOCUMENT: {item.get('document_id', 'n/a')} | VERSION: {item.get('version', 'n/a')} | TYPE: {item.get('source_type', 'trusted evidence')}\n{body}"
        )
    prompt = f"""You are VeriCommerce customer support. Answer the customer's request concisely using only the trusted evidence below.
Do not infer missing facts. Never invent amounts, dates, statuses, tracking IDs, warranty coverage, policy limits, guarantees, discounts, or customer details. If the evidence does not answer the question, clearly say so and offer support review. Do not reveal internal reasoning or secrets.

CUSTOMER QUESTION:
{user_query}

TRUSTED EVIDENCE:
{chr(10).join(evidence_blocks)}

Write only the customer-facing answer."""
    if not ollama_available():
        return _fallback(user_query, evidence)
    try:
        result = llm.invoke(prompt)
        response = strip_internal_reasoning(getattr(result, "content", ""))
        if response:
            return response[:1600]
    except Exception:
        pass
    return _fallback(user_query, evidence)
