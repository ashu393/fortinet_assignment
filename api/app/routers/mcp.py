# api/app/routers/mcp.py

from fastapi import APIRouter, Request, HTTPException, Depends
from typing import Any, Dict, Optional, List, Tuple
from pathlib import Path
from datetime import datetime

from app.security.deps import get_current_user
from app.db.models import User

from app.services.retrieval import retrieve_chunks
from app.guardrails.input import redact_pii, detect_prompt_injection, moderate_input
from app.guardrails.output import scan_output_pii
from app.llm.ollama_client import generate

from app.security.access import get_document_or_404, require_document_read_access
from app.services.contract_extract import extract_metadata_from_text

router = APIRouter()

# ---- JSON-RPC helpers ----

def rpc_result(rpc_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rpc_id, "result": result}

def rpc_error(rpc_id: Any, code: int, message: str, data: Optional[Any] = None) -> Dict[str, Any]:
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": rpc_id, "error": err}

# JSON-RPC standard-ish codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


# ---- internal helpers ----

def _parse_date_yyyy_mm_dd(s: str) -> datetime:
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except Exception:
        raise ValueError("Invalid date format, expected YYYY-MM-DD")

def _safe_read_contract_text(file_path: str, cap: int = 20000) -> str:
    fp = Path(file_path)
    if not fp.exists():
        return ""
    return fp.read_text(encoding="utf-8", errors="ignore")[:cap]

def _clause_query_for_type(clause_type: str) -> str:
    ct = (clause_type or "").strip().lower()
    mapping = {
        "termination": "terminate termination notice period for convenience",
        "renewal": "renewal auto renew automatic renewal term",
        "confidentiality": "confidential information non-disclosure disclose",
        "liability": "limitation of liability cap damages exclude consequential",
        "indemnification": "indemnify indemnification hold harmless",
        "payment": "fees payment invoice due late",
        "governing_law": "governing law jurisdiction venue",
        "privacy": "hipaa privacy security protected health information phi",
        "security": "security safeguards encryption incident breach",
    }
    return mapping.get(ct, ct or "key terms")

def _redact_tool_text(text: str) -> Tuple[str, Dict[str, int]]:
    """
    Reuse existing PII redaction guardrail for tool outputs.
    Returns (redacted_text, pii_counts)
    """
    if not text:
        return "", {"emails": 0, "ssn": 0, "phones": 0}
    redacted, meta = redact_pii(text)
    return redacted, meta

def _enforce_citations_section(answer: str, allowed_citations: List[str]) -> str:
    """
    Normalize LLM formatting drift:
    - Keep answer body
    - Add a strict "Citations:" section
    - Include only citations that appear in answer, else fall back to none
    """
    answer = (answer or "").strip()
    allowed = set([c for c in (allowed_citations or []) if c])

    used = []
    for c in allowed:
        if c in answer:
            used.append(c)

    # Remove any existing "Citations" section to avoid duplicates
    lines = answer.splitlines()
    cleaned_lines = []
    in_citations = False
    for ln in lines:
        if ln.strip().lower() == "citations:":
            in_citations = True
            continue
        if in_citations:
            # stop consuming if blank lines end or keep skipping till end
            continue
        cleaned_lines.append(ln)
    base = "\n".join(cleaned_lines).strip()

    # Add strict citations section
    out = base + "\n\nCitations:\n"
    for c in sorted(set(used)):
        out += f"- {c}\n"
    if not used:
        # keep section but empty bullets avoided; still valid
        out += ""
    return out.strip()


# ---- Tool implementations ----

def tool_search_contracts(user: User, args: Dict[str, Any]) -> Dict[str, Any]:
    if user.role == "viewer":
        raise HTTPException(status_code=403, detail="Viewers cannot search")

    query = args.get("query")
    if not query or not isinstance(query, str):
        raise ValueError("Missing/invalid 'query'")

    top_k = int(args.get("top_k", 5))
    contract_id = args.get("contract_id")

    chunks = retrieve_chunks(
        query=query,
        organization_id=user.organization_id,
        top_k=top_k,
        contract_id=contract_id,
    )

    results = []
    for c in chunks:
        snippet_raw = (c.get("text") or "")[:250]
        snippet, _ = _redact_tool_text(snippet_raw)
        results.append({
            "document_id": c["document_id"],
            "title": c.get("title"),
            "chunk_index": c["chunk_index"],
            "score": c.get("score"),
            "snippet": snippet,
            "citation": c["citation"],
        })

    return {"results": results}


def tool_ask_contracts(user: User, args: Dict[str, Any]) -> Dict[str, Any]:
    if user.role == "viewer":
        raise HTTPException(status_code=403, detail="Viewers cannot query AI")

    query = args.get("query")
    if not query or not isinstance(query, str):
        raise ValueError("Missing/invalid 'query'")

    contract_id = args.get("contract_id")
    top_k = int(args.get("top_k", 5))

    allowed, reason = moderate_input(query)
    if not allowed:
        raise ValueError(f"Blocked: {reason}")

    if detect_prompt_injection(query):
        raise ValueError("Blocked: suspected prompt injection")

    redacted_query, pii_meta = redact_pii(query)

    chunks = retrieve_chunks(
        query=redacted_query,
        organization_id=user.organization_id,
        top_k=top_k,
        contract_id=contract_id,
    )

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
        context_blocks.append(f"[{c['citation']}] {c.get('title','')}\n{c.get('text','')}")

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
    answer, out_pii = scan_output_pii(answer)
    answer = _enforce_citations_section(answer, allowed_citations)

    return {
        "answer": answer,
        "citations": allowed_citations,
        "meta": {
            "input_pii_redactions": pii_meta,
            "output_pii_redactions": out_pii,
            "retrieved_chunks": len(chunks),
            "model": "ollama/",
        },
    }


def tool_extract_metadata(user: User, args: Dict[str, Any]) -> Dict[str, Any]:
    doc_id = args.get("contract_id")
    if not doc_id or not isinstance(doc_id, str):
        raise ValueError("Missing/invalid 'contract_id'")

    require_document_read_access(user, doc_id)
    doc = get_document_or_404(doc_id)

    text = _safe_read_contract_text(doc.file_path, cap=20000)
    if not text:
        raise ValueError("Contract file not found")

    # Extractor shouldn't leak PII by design (it extracts structured fields),
    # but just in case, we can redact any strings we return later (not needed now).
    meta = extract_metadata_from_text(doc.id, doc.title, text)
    return {"metadata": meta}


def tool_extract_clause(user: User, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns clause text snippet + citations for a single contract_id.
    Uses semantic retrieval with clause-type query mapping.
    Output is PII-redacted.
    """
    if user.role == "viewer":
        raise HTTPException(status_code=403, detail="Viewers cannot query AI")

    contract_id = args.get("contract_id")
    clause_type = args.get("clause_type")
    top_k = int(args.get("top_k", 5))

    if not contract_id or not isinstance(contract_id, str):
        raise ValueError("Missing/invalid 'contract_id'")
    if not clause_type or not isinstance(clause_type, str):
        raise ValueError("Missing/invalid 'clause_type'")

    # RBAC: must be allowed to read this contract
    require_document_read_access(user, contract_id)
    get_document_or_404(contract_id)  # ensure exists

    query = _clause_query_for_type(clause_type)

    chunks = retrieve_chunks(
        query=query,
        organization_id=user.organization_id,
        top_k=top_k,
        contract_id=contract_id,
    )

    if not chunks:
        return {
            "contract_id": contract_id,
            "clause_type": clause_type,
            "text": "",
            "citations": [],
            "meta": {"pii_redactions": {"emails": 0, "ssn": 0, "phones": 0}},
        }

    citations = [c["citation"] for c in chunks]
    text_raw = "\n\n".join([(c.get("text") or "").strip() for c in chunks if (c.get("text") or "").strip()])

    # keep it small for tool output
    text_raw = text_raw[:2500]

    # redact PII from tool output
    text, pii_counts = _redact_tool_text(text_raw)

    return {
        "contract_id": contract_id,
        "clause_type": clause_type,
        "text": text,
        "citations": citations,
        "meta": {"pii_redactions": pii_counts},
    }


def tool_compare_clauses(user: User, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare clause snippets across multiple contracts.
    - clause snippets are deterministic via retrieval
    - snippets are PII-redacted
    - LLM comparison output is scanned for PII + citations normalized
    """
    if user.role == "viewer":
        raise HTTPException(status_code=403, detail="Viewers cannot query AI")

    contract_ids = args.get("contract_ids")
    clause_type = args.get("clause_type")
    top_k = int(args.get("top_k", 5))

    if not isinstance(contract_ids, list) or len(contract_ids) < 2:
        raise ValueError("'contract_ids' must be a list of at least 2 contract ids")
    if not clause_type or not isinstance(clause_type, str):
        raise ValueError("Missing/invalid 'clause_type'")

    extracted = []
    all_citations: List[str] = []

    for cid in contract_ids:
        if not isinstance(cid, str) or not cid:
            continue
        res = tool_extract_clause(user, {"contract_id": cid, "clause_type": clause_type, "top_k": top_k})
        extracted.append(res)
        all_citations.extend(res.get("citations", []))

    # Build compare context (no extra retrieval)
    context_blocks = []
    for item in extracted:
        context_blocks.append(
            f"CONTRACT {item['contract_id']} ({clause_type})\n"
            f"CITATIONS: {', '.join(item.get('citations', []))}\n"
            f"TEXT:\n{item.get('text','')}\n"
        )
    context = "\n\n---\n\n".join(context_blocks)

    allowed_citations = sorted(list({c for c in all_citations if c}))
    allowed_citations_str = ", ".join(allowed_citations)

    prompt = f"""
You are comparing contract clauses.

Rules:
- Compare ONLY the provided clause texts.
- Do not invent missing terms.
- Summarize differences and risks in 5-10 bullets.
- If a clause is missing/empty for a contract, explicitly say so.
- You may ONLY cite from: {allowed_citations_str}
- End with a section titled exactly: "Citations:" listing ONLY the citations you actually used.

Clause type: {clause_type}

Clause texts:
{context}
""".strip()

    answer = generate(prompt)
    answer, out_pii = scan_output_pii(answer)
    answer = _enforce_citations_section(answer, allowed_citations)

    return {
        "clause_type": clause_type,
        "contracts": extracted,
        "comparison": answer,
        "citations": allowed_citations,
        "meta": {
            "output_pii_redactions": out_pii,
            "model": "ollama/",
        },
    }


def tool_calculate_risk_score(user: User, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic PoC rubric.
    Returns 0-100 risk score + reasons + evidence citations.
    """
    if user.role == "viewer":
        raise HTTPException(status_code=403, detail="Viewers cannot query AI")

    contract_id = args.get("contract_id")
    if not contract_id or not isinstance(contract_id, str):
        raise ValueError("Missing/invalid 'contract_id'")

    require_document_read_access(user, contract_id)
    doc = get_document_or_404(contract_id)

    # Extract metadata
    text = _safe_read_contract_text(doc.file_path, cap=20000)
    if not text:
        raise ValueError("Contract file not found")

    meta = extract_metadata_from_text(doc.id, doc.title, text)

    score = 0
    reasons = []
    evidence = []

    # 1) Termination notice days
    notice = meta.get("termination_notice_days")
    if notice is None:
        score += 10
        reasons.append("Termination notice period not found (+10)")
    else:
        try:
            notice = int(notice)
            if notice < 30:
                score += 20
                reasons.append(f"Short termination notice ({notice} days) (+20)")
            elif notice < 60:
                score += 10
                reasons.append(f"Moderate termination notice ({notice} days) (+10)")
            else:
                reasons.append(f"Longer termination notice ({notice} days) (+0)")
        except Exception:
            score += 10
            reasons.append("Termination notice period invalid/unparseable (+10)")

    # 2) Auto-renewal
    auto_renew = meta.get("auto_renew")
    if auto_renew is True:
        score += 10
        reasons.append("Auto-renewal present (+10)")

    # 3) Liability clause presence (heuristic via retrieval)
    liab = tool_extract_clause(user, {"contract_id": contract_id, "clause_type": "liability", "top_k": 3})
    if not liab.get("text"):
        score += 15
        reasons.append("Limitation of liability clause not found (+15)")
    else:
        reasons.append("Limitation of liability clause present (+0)")
        evidence.extend(liab.get("citations", []))

    # 4) Indemnification clause presence (heuristic)
    indem = tool_extract_clause(user, {"contract_id": contract_id, "clause_type": "indemnification", "top_k": 3})
    if not indem.get("text"):
        score += 5
        reasons.append("Indemnification clause not found (+5)")
    else:
        score += 5
        reasons.append("Indemnification clause present (potentially broad) (+5)")
        evidence.extend(indem.get("citations", []))

    # 5) Governing law (simple signal)
    gov = (meta.get("governing_law") or "").lower()
    if not gov:
        score += 5
        reasons.append("Governing law not found (+5)")
    else:
        reasons.append(f"Governing law: {meta.get('governing_law')} (+0)")

    # Clamp + grade
    score = max(0, min(100, score))
    if score >= 60:
        grade = "High"
    elif score >= 30:
        grade = "Medium"
    else:
        grade = "Low"

    evidence = sorted(list({c for c in evidence if c}))

    return {
        "contract_id": contract_id,
        "title": doc.title,
        "risk_score": score,
        "risk_grade": grade,
        "reasons": reasons,
        "evidence_citations": evidence,
        "metadata_used": {
            "effective_date": meta.get("effective_date"),
            "term": meta.get("term"),
            "auto_renew": meta.get("auto_renew"),
            "termination_notice_days": meta.get("termination_notice_days"),
            "governing_law": meta.get("governing_law"),
        },
    }


def tool_find_expiring_contracts(user: User, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Spec-aligned signature:
      - start_date: YYYY-MM-DD
      - end_date: YYYY-MM-DD
      - auto_renewal_only: bool (optional)
    """
    start_date = args.get("start_date")
    end_date = args.get("end_date")
    auto_only = bool(args.get("auto_renewal_only", False))

    if not start_date or not isinstance(start_date, str):
        raise ValueError("Missing/invalid 'start_date' (YYYY-MM-DD)")
    if not end_date or not isinstance(end_date, str):
        raise ValueError("Missing/invalid 'end_date' (YYYY-MM-DD)")

    start = _parse_date_yyyy_mm_dd(start_date)
    end = _parse_date_yyyy_mm_dd(end_date)
    if end <= start:
        raise ValueError("'end_date' must be after 'start_date'")

    from app.db.session import SessionLocal
    from app.db.models import Document

    db = SessionLocal()
    docs = db.query(Document).filter(Document.organization_id == user.organization_id).all()

    matches = []
    for d in docs:
        fp = Path(d.file_path)
        if not fp.exists():
            continue

        text = fp.read_text(encoding="utf-8", errors="ignore")[:20000]
        meta = extract_metadata_from_text(d.id, d.title, text)

        if auto_only and meta.get("auto_renew") is not True:
            continue

        eff = meta.get("effective_date")
        if not eff:
            continue

        try:
            eff_dt = datetime.strptime(eff, "%Y-%m-%d")
        except Exception:
            continue

        # default assumption: 1 year term if not present
        exp_dt = eff_dt.replace(year=eff_dt.year + 1)

        term = meta.get("term")
        if term:
            try:
                num, unit = term.split(" ", 1)
                num = int(num)
                unit = unit.lower()
                if "year" in unit:
                    exp_dt = eff_dt.replace(year=eff_dt.year + num)
                elif "month" in unit:
                    month = eff_dt.month + num
                    year = eff_dt.year + (month - 1) // 12
                    month = ((month - 1) % 12) + 1
                    exp_dt = eff_dt.replace(year=year, month=month)
            except Exception:
                pass

        if start <= exp_dt < end:
            matches.append({
                "contract_id": d.id,
                "title": d.title,
                "effective_date": meta.get("effective_date"),
                "assumed_expiry_date": exp_dt.strftime("%Y-%m-%d"),
                "auto_renew": meta.get("auto_renew"),
                "termination_notice_days": meta.get("termination_notice_days"),
            })

    db.close()

    matches.sort(key=lambda x: x["assumed_expiry_date"])

    return {
        "window": {"start": start.strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d")},
        "auto_renewal_only": auto_only,
        "expiring": matches,
    }


# ---- MCP JSON-RPC endpoint ----

@router.post("")
async def mcp_rpc(request: Request, user: User = Depends(get_current_user)):
    try:
        payload = await request.json()
    except Exception:
        return rpc_error(None, PARSE_ERROR, "Parse error")

    if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0":
        return rpc_error(payload.get("id") if isinstance(payload, dict) else None, INVALID_REQUEST, "Invalid Request")

    rpc_id = payload.get("id")
    method = payload.get("method")
    params = payload.get("params") or {}

    if not method or not isinstance(method, str):
        return rpc_error(rpc_id, INVALID_REQUEST, "Invalid Request")

    try:
        if method == "initialize":
            return rpc_result(rpc_id, {
                "serverInfo": {"name": "contract-intel-mcp", "version": "0.1"},
                "capabilities": {"tools": True},
            })

        if method == "tools/list":
            tools = [
                {
                    "name": "search_contracts",
                    "description": "Semantic search across tenant contracts (Qdrant).",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "top_k": {"type": "integer", "default": 5},
                            "contract_id": {"type": ["string", "null"]},
                        },
                        "required": ["query"],
                    },
                },
                {
                    "name": "extract_clause",
                    "description": "Extract a clause snippet from a contract (termination, renewal, confidentiality, liability, indemnification, payment, governing_law).",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "contract_id": {"type": "string"},
                            "clause_type": {"type": "string"},
                            "top_k": {"type": "integer", "default": 5},
                        },
                        "required": ["contract_id", "clause_type"],
                    },
                },
                {
                    "name": "compare_clauses",
                    "description": "Compare a clause across multiple contracts and highlight differences.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "contract_ids": {"type": "array", "items": {"type": "string"}},
                            "clause_type": {"type": "string"},
                            "top_k": {"type": "integer", "default": 5},
                        },
                        "required": ["contract_ids", "clause_type"],
                    },
                },
                {
                    "name": "extract_metadata",
                    "description": "Extract key contract metadata (effective date, term, notice, governing law).",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "contract_id": {"type": "string"},
                        },
                        "required": ["contract_id"],
                    },
                },
                {
                    "name": "calculate_risk_score",
                    "description": "Compute a PoC risk score (0-100) for a contract using metadata + key clauses.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "contract_id": {"type": "string"},
                        },
                        "required": ["contract_id"],
                    },
                },
                {
                    "name": "find_expiring_contracts",
                    "description": "Find contracts expiring within a date range (tenant-scoped).",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
                            "auto_renewal_only": {"type": "boolean", "default": False},
                        },
                        "required": ["start_date", "end_date"],
                    },
                },
                {
                    "name": "ask_contracts",
                    "description": "Answer a question using RAG over tenant contracts with citations.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "top_k": {"type": "integer", "default": 5},
                            "contract_id": {"type": ["string", "null"]},
                        },
                        "required": ["query"],
                    },
                },
            ]
            return rpc_result(rpc_id, {"tools": tools})

        if method == "tools/call":
            name = params.get("name")
            args = params.get("arguments") or {}

            if name == "search_contracts":
                return rpc_result(rpc_id, tool_search_contracts(user, args))

            if name == "ask_contracts":
                return rpc_result(rpc_id, tool_ask_contracts(user, args))

            if name == "extract_clause":
                return rpc_result(rpc_id, tool_extract_clause(user, args))

            if name == "compare_clauses":
                return rpc_result(rpc_id, tool_compare_clauses(user, args))

            if name == "extract_metadata":
                return rpc_result(rpc_id, tool_extract_metadata(user, args))

            if name == "calculate_risk_score":
                return rpc_result(rpc_id, tool_calculate_risk_score(user, args))

            if name == "find_expiring_contracts":
                return rpc_result(rpc_id, tool_find_expiring_contracts(user, args))

            return rpc_error(rpc_id, METHOD_NOT_FOUND, f"Tool not found: {name}")

        return rpc_error(rpc_id, METHOD_NOT_FOUND, f"Method not found: {method}")

    except ValueError as ve:
        return rpc_error(rpc_id, INVALID_PARAMS, str(ve))
    except HTTPException as he:
        return rpc_error(rpc_id, INTERNAL_ERROR, he.detail)
    except Exception as e:
        return rpc_error(rpc_id, INTERNAL_ERROR, "Internal error", data=str(e))