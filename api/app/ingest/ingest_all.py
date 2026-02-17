import os
import uuid
from pathlib import Path
from typing import List, Dict, Any, Tuple

import httpx
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from app.config import settings
from app.db.session import SessionLocal
from app.db.models import Document


def chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    text = text.replace("\r\n", "\n")
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        chunks.append(text[start:end])
        if end == n:
            break
        start = max(0, end - overlap)
    return chunks


def ollama_embed(text: str, base_url: str, model: str) -> List[float]:
    cleaned = "".join(ch for ch in text if ch == "\n" or (32 <= ord(ch) <= 126))

    max_chars = int(os.getenv("EMBED_TEXT_MAX_CHARS", "1200"))
    cleaned = cleaned[:max_chars]

    url = f"{base_url}/api/embeddings"
    payload = {"model": model, "prompt": cleaned}

    with httpx.Client(timeout=60.0) as client:
        r = client.post(url, json=payload)
        r.raise_for_status()
        return r.json()["embedding"]

def ensure_collection(client: QdrantClient, collection: str, vector_size: int):
    existing = [c.name for c in client.get_collections().collections]
    if collection in existing:
        return
    client.create_collection(
        collection_name=collection,
        vectors_config=qm.VectorParams(size=vector_size, distance=qm.Distance.COSINE),
    )


def ingest_all():
    base_url = settings.ollama_base_url
    embed_model = os.getenv("EMBED_MODEL", "mxbai-embed-large")
    collection = os.getenv("QDRANT_COLLECTION", "contracts_chunks")
    chunk_size = int(os.getenv("CHUNK_SIZE", "1200"))
    overlap = int(os.getenv("CHUNK_OVERLAP", "200"))

    # Qdrant inside docker network
    qdrant_url = os.getenv("QDRANT_URL", "http://qdrant:6333")
    qdrant = QdrantClient(url=qdrant_url)

    db = SessionLocal()
    docs = db.query(Document).all()
    if not docs:
        db.close()
        raise RuntimeError("No documents in DB. Run seed_docs.py first.")

    # Determine embedding vector size once
    probe_vec = ollama_embed("vector size probe", base_url, embed_model)
    vector_size = len(probe_vec)

    ensure_collection(qdrant, collection, vector_size)

    points: List[qm.PointStruct] = []
    total_chunks = 0

    for doc in docs:
        fp = Path(doc.file_path)
        if not fp.exists():
            print(f"⚠️ Missing file: {doc.file_path} (skipping)")
            continue

        text = fp.read_text(encoding="utf-8", errors="ignore")
        chunks = chunk_text(text, chunk_size, overlap)

        for idx, ch in enumerate(chunks):
            vec = ollama_embed(ch, base_url, embed_model)
            payload: Dict[str, Any] = {
                "organization_id": doc.organization_id,
                "document_id": doc.id,
                "title": doc.title,
                "chunk_index": idx,
                "text": ch,
            }
            points.append(
                qm.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vec,
                    payload=payload,
                )
            )
            total_chunks += 1

            # batch flush to qdrant
            if len(points) >= 64:
                qdrant.upsert(collection_name=collection, points=points)
                points.clear()

        print(f"✅ Ingested {doc.id} ({len(chunks)} chunks)")

    if points:
        qdrant.upsert(collection_name=collection, points=points)

    db.close()
    print(f"\n🎉 Done. Total chunks indexed: {total_chunks}")
    print(f"Collection: {collection} | Vector size: {vector_size} | Qdrant: {qdrant_url}")


if __name__ == "__main__":
    ingest_all()