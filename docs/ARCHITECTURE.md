# ARCHITECTURE — Contract Intelligence MCP Server

---

# 1. Overview

The system is a **multi-tenant contract intelligence platform** exposing tools through an **MCP-compatible JSON-RPC interface**.

It enables:

* Semantic contract search
* Clause extraction
* Cross-contract comparison
* Metadata extraction
* Risk scoring
* Expiry analysis

The design prioritizes:

* tenant isolation
* deterministic retrieval
* guardrailed LLM usage
* reproducible outputs

---

# 2. High Level Architecture

```
Client
   ↓
FastAPI API Layer
   ↓
Auth + RBAC
   ↓
MCP Router (JSON-RPC)
   ↓
Tool Handlers
   ↓
Retrieval / Metadata / Risk Logic
   ↓
Qdrant Vector DB + Contract Files
   ↓
Ollama LLM (local)
```

---

# 3. Core Components

---

## 3.1 API Layer

Implemented with:

```
FastAPI
```

Responsibilities:

* authentication
* RBAC enforcement
* JSON-RPC endpoint for MCP
* REST endpoints for chat and search

---

## 3.2 MCP Router

Implements JSON-RPC 2.0.

Supported methods:

* initialize
* tools/list
* tools/call

This allows external AI clients to treat the service as an MCP tool provider.

No external MCP library is required — MCP is treated as a protocol specification.

---

## 3.3 Retrieval Pipeline (RAG)

### Ingestion

Contracts are:

* chunked into text blocks
* embedded using Ollama embedding model
* stored in Qdrant

Each vector stores:

* organization_id
* contract_id
* chunk_index
* title
* text

---

### Query Flow

```
User Query
   ↓
Guardrails
   ↓
Embedding
   ↓
Qdrant semantic search
   ↓
Top-K chunks returned
   ↓
LLM receives ONLY retrieved context
```

The LLM is never allowed to answer without retrieved context.

If no chunks are found:

```
"Not found in the provided contracts."
```

---

# 4. Multi-Tenant Security Model

Tenant isolation is enforced in multiple layers.

---

## Layer 1 — Authentication

Users log in and receive a JWT.

JWT contains:

* user_id
* organization_id
* role

---

## Layer 2 — RBAC

Roles:

* admin
* analyst
* viewer

Restrictions:

* viewer cannot query AI
* viewer cannot search contracts

---

## Layer 3 — Vector Filtering

Every retrieval call includes:

```
organization_id filter
```

This prevents cross-tenant vector access.

---

## Layer 4 — File Access Validation

Before reading any contract file:

```
require_document_read_access(user, contract_id)
```

This prevents unauthorized local file reads.

---

# 5. Guardrails

Guardrails are applied both **before** and **after** the LLM.

---

## Input Guardrails

* prompt injection detection
* content moderation
* PII detection and redaction

---

## Output Guardrails

* scan for leaked PII
* redact emails / SSNs / phone numbers

---

# 6. Tool Architecture

Each MCP tool follows a consistent structure.

```
Validate input
Check RBAC
Retrieve contract data
Apply deterministic logic
Optionally invoke LLM with restricted context
Return structured JSON
```

---

## Deterministic Tools

These do NOT rely on LLM hallucination:

* extract_metadata
* calculate_risk_score
* find_expiring_contracts

---

## Retrieval-Based Tools

These use vector search:

* search_contracts
* extract_clause
* ask_contracts

---

## Hybrid Tool

```
compare_clauses
```

Steps:

1. Retrieve clause snippets deterministically
2. Pass snippets to LLM
3. LLM compares ONLY provided text

This prevents hallucinated contract terms.

---

# 7. Risk Scoring Logic

Risk score is computed using a deterministic rubric.

Signals include:

* short termination notice
* auto-renewal presence
* liability clause absence
* indemnification presence
* governing law availability

The score is bounded:

```
0-100
```

and mapped to:

```
Low / Medium / High
```

---

# 8. Expiry Detection Logic

Expiry is calculated using:

```
effective_date + term
```

If term missing:

```
assume 1 year (PoC default)
```

Supports filtering:

* start_date
* end_date
* auto_renewal_only

---

# 9. LLM Usage Strategy

The LLM is used only when necessary.

Principles:

* never allow free-form answering
* always restrict to retrieved context
* explicitly list allowed citations
* enforce structured answers

This reduces hallucination risk.

---

# 10. Why This Architecture

This design was chosen because it:

* enforces tenant security at multiple layers
* separates deterministic vs LLM logic
* ensures reproducible outputs
* minimizes hallucination risk
* supports MCP protocol integration

---

# 11. Future Improvements

Possible production extensions:

* streaming MCP responses
* audit logging of tool usage
* clause classifier for better extraction
* incremental ingestion
* contract upload API
* structured metadata storage