"""RAG ingestion (placeholder):
- PDF -> text extraction (sections + page numbers)
- chunking strategy
- embeddings
- upsert into Qdrant with metadata: org_id, contract_id, section, page, tags
"""

def ingest_pdf(contract_id: str, org_id: str, file_path: str):
    raise NotImplementedError
