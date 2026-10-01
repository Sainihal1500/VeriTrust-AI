"""Build the Chroma policy collection while preserving the last good index."""

from pathlib import Path
import os
import re

import chromadb
from langchain_ollama import OllamaEmbeddings

BASE_DIR = Path(__file__).resolve().parents[2]
KNOWLEDGE_BASE = BASE_DIR / "data" / "knowledge_base"
CHROMA_PATH = BASE_DIR / "data" / "chroma"
COLLECTION_NAME = "veritrust_knowledge"
STAGING_NAME = "veritrust_knowledge_staging"
BACKUP_NAME = "veritrust_knowledge_backup"

client = chromadb.PersistentClient(path=str(CHROMA_PATH))
embeddings = OllamaEmbeddings(model="nomic-embed-text:latest", base_url=os.getenv("OLLAMA_BASE_URL") or None, client_kwargs={"timeout": 60})


def chunk_document(text: str, max_chars: int = 1200):
    sections = [part.strip() for part in re.split(r"\n(?=\d+\.\s+)", text) if part.strip()]
    chunks = []
    for section in sections:
        if len(section) <= max_chars:
            chunks.append(section)
            continue
        paragraphs = re.split(r"\n\s*\n", section)
        current = ""
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            if current and len(current) + len(paragraph) + 2 > max_chars:
                chunks.append(current)
                current = ""
            if len(paragraph) > max_chars:
                words = paragraph.split()
                for word in words:
                    if current and len(current) + len(word) + 1 > max_chars:
                        chunks.append(current)
                        current = ""
                    current = f"{current} {word}".strip()
            else:
                current = f"{current}\n\n{paragraph}".strip()
        if current:
            chunks.append(current)
    return chunks


def extract_metadata(file_path: Path):
    text = file_path.read_text(encoding="utf-8")
    fields = {}
    for name in ("Document ID", "Version", "Effective Date", "Source Type"):
        match = re.search(rf"^{re.escape(name)}:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE)
        fields[name.casefold().replace(" ", "_")] = match.group(1).strip() if match else None
    category = file_path.parent.name if file_path.parent != KNOWLEDGE_BASE else "refund"
    return {
        "document_id": fields["document_id"] or file_path.stem.upper().replace("_", "-"),
        "document_name": file_path.name,
        "category": category,
        "version": fields["version"] or "1.0",
        "effective_date": fields["effective_date"] or "unknown",
        "source_type": fields["source_type"] or "official_internal_policy",
    }


def _copy_collection(source, target):
    offset = 0
    while True:
        records = source.get(offset=offset, limit=256, include=["documents", "metadatas", "embeddings"])
        ids = records.get("ids", [])
        if not ids:
            break
        vectors = records.get("embeddings")
        if hasattr(vectors, "tolist"):
            vectors = vectors.tolist()
        target.add(ids=ids, documents=records.get("documents"), metadatas=records.get("metadatas"), embeddings=vectors)
        offset += len(ids)


def _delete_if_exists(name: str):
    try:
        client.delete_collection(name)
    except Exception:
        pass


def ingest_documents():
    files = sorted(KNOWLEDGE_BASE.rglob("*.txt"))
    if not files:
        raise FileNotFoundError(f"No policy documents found under {KNOWLEDGE_BASE}")

    records = []
    for file_path in files:
        metadata = extract_metadata(file_path)
        for index, chunk in enumerate(chunk_document(file_path.read_text(encoding="utf-8"))):
            records.append((f"{metadata['document_id']}-{index:04d}", chunk, metadata))

    _delete_if_exists(STAGING_NAME)
    staging = client.create_collection(name=STAGING_NAME, metadata={"hnsw:space": "cosine"})
    try:
        for start in range(0, len(records), 32):
            batch = records[start:start + 32]
            vectors = embeddings.embed_documents([item[1] for item in batch])
            staging.add(
                ids=[item[0] for item in batch],
                documents=[item[1] for item in batch],
                metadatas=[item[2] for item in batch],
                embeddings=vectors,
            )

        _delete_if_exists(BACKUP_NAME)
        try:
            current = client.get_collection(COLLECTION_NAME)
        except Exception:
            current = None
        if current is not None:
            backup = client.create_collection(name=BACKUP_NAME, metadata={"hnsw:space": "cosine"})
            _copy_collection(current, backup)

        _delete_if_exists(COLLECTION_NAME)
        replacement = client.create_collection(name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"})
        try:
            _copy_collection(staging, replacement)
        except Exception:
            _delete_if_exists(COLLECTION_NAME)
            try:
                backup = client.get_collection(BACKUP_NAME)
                restored = client.create_collection(name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"})
                _copy_collection(backup, restored)
            except Exception:
                pass
            raise
        total = replacement.count()
        _delete_if_exists(BACKUP_NAME)
        _delete_if_exists(STAGING_NAME)
        return {"documents": len(files), "chunks": len(records), "collection_count": total, "collection": COLLECTION_NAME}
    except Exception:
        _delete_if_exists(STAGING_NAME)
        raise


if __name__ == "__main__":
    summary = ingest_documents()
    print("VeriTrust knowledge base rebuilt successfully")
    for key, value in summary.items():
        print(f"{key}: {value}")
