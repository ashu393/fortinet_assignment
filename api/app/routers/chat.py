# api/app/routers/chat.py

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.security.deps import get_current_user
from app.db.models import User
from app.guardrails.input import redact_pii, detect_prompt_injection, moderate_input
from app.guardrails.output import scan_output_pii
from app.llm.ollama_client import generate
from app.services.retrieval import retrieve_chunks

router = APIRouter()


class ChatQuery(BaseModel):
    query: str
    contract_id: str | None = None
    top_k: int = 5


@router.post("/query")
def query_contracts(payload: ChatQuery, user: User = Depends(get_current_user)):
    # RBAC: viewers cannot query AI
    if user.role == "viewer":
        raise HTTPException(status_code=403, detail="Viewers cannot query AI")

    # Input guardrails
    allowed, reason = moderate_input(payload.query)
    if not allowed:
        raise HTTPException(status_code=400, detail=f"Blocked: {reason}")

    if detect_prompt_injection(payload.query):
        raise HTTPException(status_code=400, detail="Blocked: suspected prompt injection")

    redacted_query, pii_meta = redact_pii(payload.query)

    # Retrieve top chunks (org-filtered, optional contract filter)
    chunks = retrieve_chunks(
        query=redacted_query,
        organization_id=user.organization_id,
        top_k=payload.top_k,
        contract_id=payload.contract_id,
    )

    # Hard anti-hallucination gate: no retrieved context => no LLM call
    if not chunks:
        return {
            "answer": "Not found in the provided contracts.",
            "citations": [],
            "meta": {
                "input_pii_redactions": pii_meta,
                "output_pii_redactions": {"emails": 0, "ssn": 0, "phones": 0},
                "retrieved_chunks": 0,
                "model": "ollama/",
            },
        }

    context_blocks = []
    allowed_citations = []
    for c in chunks:
        allowed_citations.append(c["citation"])
        context_blocks.append(f"[{c['citation']}] {c.get('title', '')}\n{c.get('text', '')}")

    context = "\n\n---\n\n".join(context_blocks)
    allowed_citations_str = ", ".join(allowed_citations)

    prompt = f"""
You are a contract analysis assistant.

Rules:
- Use ONLY the provided context to answer.
- If the answer is not in the context, say exactly: "Not found in the provided contracts."
- Do NOT reveal any PII. If present, redact emails/SSNs/phones.
- Be concise.
- You are ONLY allowed to cite from this exact list: {allowed_citations_str}
- End your answer with a section exactly titled: "Citations:" and list bullet points of ONLY the citations you actually used.

User question:
{redacted_query}

Context:
{context}
""".strip()

    answer = generate(prompt)

    # Output guardrails
    answer, out_pii = scan_output_pii(answer)

    return {
        "answer": answer,
        "citations": allowed_citations,  # retrieved citations (allowed list)
        "meta": {
            "input_pii_redactions": pii_meta,
            "output_pii_redactions": out_pii,
            "retrieved_chunks": len(chunks),
            "model": "ollama/",
        },
    }