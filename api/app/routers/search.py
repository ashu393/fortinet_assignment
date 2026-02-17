import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from app.security.deps import get_current_user
from app.db.models import User
from app.ingest.ingest_all import ollama_embed

router = APIRouter()

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    contract_id: Optional[str] = None


@router.post("/contracts")
def search_contracts(payload: SearchRequest, user: User = Depends(get_current_user)):

    # viewers blocked
    if user.role == "viewer":
        raise HTTPException(status_code=403, detail="Viewers cannot search")

    qdrant = QdrantClient(url=os.getenv("QDRANT_URL", "http://qdrant:6333"))

    qvec = ollama_embed(
        payload.query,
        os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"),
        os.getenv("EMBED_MODEL", "mxbai-embed-large"),
    )

    must = [
        qm.FieldCondition(
            key="organization_id",
            match=qm.MatchValue(value=user.organization_id)
        )
    ]

    if payload.contract_id:
        must.append(
            qm.FieldCondition(
                key="document_id",
                match=qm.MatchValue(value=payload.contract_id)
            )
        )

    hits = qdrant.search(
        collection_name=os.getenv("QDRANT_COLLECTION", "contracts_chunks"),
        query_vector=qvec,
        query_filter=qm.Filter(must=must),
        limit=payload.top_k,
        with_payload=True,
    )

    results = []

    for h in hits:
        p = h.payload
        results.append({
            "document_id": p["document_id"],
            "title": p["title"],
            "score": h.score,
            "snippet": p["text"][:250],
            "citation": f'{p["document_id"]}#chunk-{p["chunk_index"]}'
        })

    return {"results": results}