"""Category-aware policy retrieval with a lexical fallback when Ollama is down."""

from pathlib import Path
import os
import re

import chromadb
from langchain_ollama import OllamaEmbeddings
from agents.llm_utils import ollama_available

BASE_DIR = Path(__file__).resolve().parents[2]
KNOWLEDGE_BASE = BASE_DIR / "data" / "knowledge_base"
CHROMA_PATH = BASE_DIR / "data" / "chroma"
CATEGORY_MAPPING = {
    "refund": {"refund", "refunds", "payments"},
    "return": {"return", "returns", "refund"},
    "cancellation": {"cancellation", "orders"},
    "shipping": {"shipping", "orders", "support"},
    "payment": {"payments", "refund", "support"},
    "warranty": {"warranty", "products", "support"},
    "promotion": {"promotions", "support"},
    "security": {"security", "privacy"},
    "privacy": {"privacy", "security"},
    "product": {"products", "warranty"},
    "order": {"orders", "shipping", "cancellation"},
    "general": {"support", "orders"},
}

client = chromadb.PersistentClient(path=str(CHROMA_PATH))
embeddings = OllamaEmbeddings(model="nomic-embed-text:latest", base_url=os.getenv("OLLAMA_BASE_URL") or None, client_kwargs={"timeout": 10})


def _metadata(item: dict):
    return {key: item.get(key, "unknown") for key in ("document_id", "document_name", "category", "version", "effective_date", "source_type")}


def _lexical_retrieval(query: str, category: str, n_results: int):
    query_terms = {token for token in re.findall(r"[a-z0-9]+", query.casefold()) if len(token) > 2}
    preferred = CATEGORY_MAPPING.get(category, CATEGORY_MAPPING["general"])
    candidates = []
    for path in sorted(KNOWLEDGE_BASE.rglob("*.txt")):
        text = path.read_text(encoding="utf-8")
        metadata_match = re.search(r"Document ID:\s*(.+)", text)
        version_match = re.search(r"Version:\s*(.+)", text)
        date_match = re.search(r"Effective Date:\s*(.+)", text)
        category_name = path.parent.name if path.parent != KNOWLEDGE_BASE else "refund"
        sections = re.split(r"\n(?=\d+\.\s+)", text)
        for chunk_index, chunk in enumerate(sections):
            chunk = re.sub(r"\s+", " ", chunk).strip()
            if len(chunk) < 50:
                continue
            chunk_terms = set(re.findall(r"[a-z0-9]+", chunk.casefold()))
            overlap = len(query_terms & chunk_terms)
            score = overlap / max(1, len(query_terms))
            category_match = category_name in preferred
            if category_match:
                score += 0.12
            if score <= 0:
                continue
            candidates.append({
                "text": chunk,
                "source": path.name,
                "document_id": metadata_match.group(1).strip() if metadata_match else path.stem.upper(),
                "category": category_name,
                "version": version_match.group(1).strip() if version_match else "unknown",
                "effective_date": date_match.group(1).strip() if date_match else "unknown",
                "source_type": "official_internal_policy",
                "distance": round(1.0 - score, 4),
                "similarity_score": round(score, 4),
                "category_match": category_match,
                "chunk_id": f"{path.stem}-{chunk_index}",
            })
    candidates.sort(key=lambda item: (not item["category_match"], item["distance"]))
    return candidates[:n_results]


def retrieve_evidence(query: str, category: str = "general", n_results: int = 5):
    """Return source-tracked policy passages; an empty result is safe on failure."""
    category = category if category in CATEGORY_MAPPING else "general"
    n_results = max(1, min(int(n_results), 12))
    if not ollama_available():
        return _lexical_retrieval(query, category, n_results)
    try:
        collection = client.get_collection(name="veritrust_knowledge")
        count = collection.count()
    except Exception:
        return _lexical_retrieval(query, category, n_results)
    if count == 0:
        return _lexical_retrieval(query, category, n_results)

    try:
        vector = embeddings.embed_query(query)
        candidate_count = min(count, max(n_results * 5, 20))
        result = collection.query(query_embeddings=[vector], n_results=candidate_count)
        preferred = CATEGORY_MAPPING[category]
        evidence = []
        for document, metadata, distance, record_id in zip(
            result.get("documents", [[]])[0],
            result.get("metadatas", [[]])[0],
            result.get("distances", [[]])[0],
            result.get("ids", [[]])[0],
        ):
            metadata = metadata or {}
            category_match = metadata.get("category") in preferred
            # A small category preference keeps semantic relevance meaningful.
            adjusted = float(distance) - (0.12 if category_match else 0)
            evidence.append({
                "text": document,
                "source": metadata.get("document_name", "unknown"),
                "document_id": metadata.get("document_id", "unknown"),
                "category": metadata.get("category", "unknown"),
                "version": metadata.get("version", "unknown"),
                "effective_date": metadata.get("effective_date", "unknown"),
                "source_type": metadata.get("source_type", "official_internal_policy"),
                "distance": round(float(distance), 6),
                "adjusted_distance": round(adjusted, 6),
                "similarity_score": round(1 / (1 + max(float(distance), 0)), 6),
                "category_match": category_match,
                "chunk_id": record_id,
            })
        evidence.sort(key=lambda item: (not item["category_match"], item["adjusted_distance"]))
        # Only fill category results with cross-category matches if necessary.
        if evidence and not any(item["category_match"] for item in evidence[:n_results]):
            lexical = _lexical_retrieval(query, category, n_results)
            if lexical:
                return lexical
        return evidence[:n_results]
    except Exception:
        return _lexical_retrieval(query, category, n_results)
