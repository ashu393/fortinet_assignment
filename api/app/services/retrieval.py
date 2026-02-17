import os
from typing import List, Dict, Any, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from app.ingest.ingest_all import ollama_embed

def retrieve_chunks(
    query: str,
    organization_id: str,
    top_k: int = 5,
    contract_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    qdrant = QdrantClient(url=os.getenv("QDRANT_URL", "http://qdrant:6333"))

    qvec = ollama_embed(
        query,
        os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"),
        os.getenv("EMBED_MODEL", "mxbai-embed-large"),
    )

    must = [
        qm.FieldCondition(key="organization_id", match=qm.MatchValue(value=organization_id))
    ]
    if contract_id:
        must.append(qm.FieldCondition(key="document_id", match=qm.MatchValue(value=contract_id)))

    hits = qdrant.search(
        collection_name=os.getenv("QDRANT_COLLECTION", "contracts_chunks"),
        query_vector=qvec,
        query_filter=qm.Filter(must=must),
        limit=min(max(top_k, 1), 10),
        with_payload=True,
    )

    out: List[Dict[str, Any]] = []
    for h in hits:
        p = h.payload or {}
        doc_id = p.get("document_id")
        chunk_index = p.get("chunk_index")
        out.append({
            "document_id": doc_id,
            "chunk_index": chunk_index,
            "title": p.get("title"),
            "score": h.score,
            "text": (p.get("text") or "").strip(),
            "citation": f"{doc_id}#chunk-{chunk_index}",
        })
    return out