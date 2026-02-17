# Contract Intelligence MCP Server (RAG + Guardrails + Multi-Tenant)

## Overview

This project implements a **multi-tenant contract intelligence system** exposing an **MCP-compatible JSON-RPC API**.

It supports:

* Semantic contract search (Qdrant)
* Retrieval-augmented answers with citations
* Clause extraction and comparison
* Metadata extraction
* Risk scoring
* Expiring contract detection
* Prompt-injection protection
* PII redaction
* Tenant isolation + RBAC enforcement

The system is designed as a **secure contract analysis backend** suitable for enterprise environments.

---

## Architecture

**Core Components**

* FastAPI backend (API + MCP endpoint)
* Qdrant vector database
* Ollama local LLM (Qwen + embedding model)
* Seeded contract dataset
* Guardrails layer (input/output protection)

---

## Features

### Multi-Tenant Security

* JWT authentication
* Organization-scoped document access
* Viewer role cannot use AI or search
* Cross-tenant data access blocked

---

### Guardrails

* Prompt injection detection
* Input PII redaction
* Output PII scanning
* Moderation filter

---

### Retrieval-Augmented Generation

Contracts are:

1. Chunked
2. Embedded
3. Stored in Qdrant

Queries:

1. Retrieve top semantic matches
2. Build context
3. Generate answer using Ollama
4. Return citations

---

## MCP JSON-RPC Endpoint

```
POST /mcp
```

Supported methods:

* initialize
* tools/list
* tools/call

---

## Available Tools

| Tool                    | Description                             |
| ----------------------- | --------------------------------------- |
| search_contracts        | Semantic search across contracts        |
| ask_contracts           | Ask questions with RAG + citations      |
| extract_clause          | Extract specific clause text            |
| compare_clauses         | Compare clauses across contracts        |
| extract_metadata        | Extract contract metadata               |
| calculate_risk_score    | Compute deterministic risk score        |
| find_expiring_contracts | Detect contracts expiring in date range |

---

## How To Run

### 0. Clone the repo

```
git clone https://github.com/ashu393/fortinet_assignment.git
```

---

### 1. Start services

```
docker compose up --build -d
```

### 2. Load models into Ollama containers (LLM + Embedding models)

```
docker exec -it <ollama-container-name> ollama pull qwen2.5:7b-instruct-q4_K_M

docker exec -it <ollama-container-name> ollama pull mxbai-embed-large
```

---

### 3. Init and Seed database (users + contracts)

```
docker exec -it <api-container> python -m app.db.init_db

docker exec -it -e PYTHONPATH=/app <api-container> python app/db/seed_docs.py
```

---

### 4. Ingest contracts into Qdrant

```
docker exec -it -e PYTHONPATH=/app <api-container> python /app/app/ingest/ingest_all.py
```

---

### 5. Verify API

```
curl http://localhost:8000/health
```

---

## Login Example

```
curl -X POST http://localhost:8000/auth/login \
-H "Content-Type: application/json" \
-d '{"email":"bob@techcorp.com","password":"Bob@123"}'
```

Use returned token for Authorization header.

---

## Example MCP Call

```
curl -X POST http://localhost:8000/mcp \
-H "Authorization: Bearer TOKEN" \
-H "Content-Type: application/json" \
-d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

---

## Test Cases / Simulation

### 1. Login as Bob (analyst) + store token

```
BOB_TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"bob@techcorp.com","password":"Bob@123"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "BOB_TOKEN loaded: " $(echo $BOB_TOKEN | cut -c1-25)"..."
```

#### Response
```
BOB_TOKEN loaded:  eyJhbGciOiJIUzI1NiIsInR5c...
```

---

### 2.Login as Charlie (viewer) + store token

```
CHARLIE_TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"charlie@techcorp.com","password":"Charlie@123"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "CHARLIE_TOKEN loaded: " $(echo $CHARLIE_TOKEN | cut -c1-25)"..."
```

#### Response
```
CHARLIE_TOKEN loaded:  eyJhbGciOiJIUzI1NiIsInR5c...
```

---

### 3.Viewer RBAC: viewer cannot search

```
curl -i -s -X POST http://localhost:8000/search/contracts \
  -H "Authorization: Bearer ${CHARLIE_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"query":"termination notice", "top_k": 3}'
```
#### Expected: 403 with "Viewers cannot search".

#### Response
```
HTTP/1.1 403 Forbidden
date: Tue, 17 Feb 2026 18:45:16 GMT
server: uvicorn
content-length: 34
content-type: application/json

{"detail":"Viewers cannot search"}%
```

---

### 4.Viewer RBAC: viewer cannot query AI

```
curl -i -s -X POST http://localhost:8000/chat/query \
  -H "Authorization: Bearer ${CHARLIE_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"query":"What is the termination notice period?", "top_k": 3}'
```
#### Expected: 403 with "Viewers cannot query AI".

#### Response
```
HTTP/1.1 403 Forbidden
date: Tue, 17 Feb 2026 18:45:45 GMT
server: uvicorn
content-length: 36
content-type: application/json

{"detail":"Viewers cannot query AI"}%   
```

---

### 5.Bob semantic search across tenant contracts

```
curl -s -X POST http://localhost:8000/search/contracts \
  -H "Authorization: Bearer ${BOB_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"query":"termination notice period", "top_k": 5}' | python -m json.tool
```
#### Expected: results with document_id, score, snippet, citation.

---

### 6.Bob semantic search with contract filter

```
curl -s -X POST http://localhost:8000/search/contracts \
  -H "Authorization: Bearer ${BOB_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"query":"termination notice", "top_k": 5, "contract_id":"TC-1055"}' | python -m json.tool
```

---

### 7.Bob RAG Q&A with citations

```
curl -s -X POST http://localhost:8000/chat/query \
  -H "Authorization: Bearer ${BOB_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"query":"What is the termination notice period?","contract_id":"TC-1055","top_k":5}' \
  | python -m json.tool
```
#### Expected: answer + citations like



---

## Repository Structure

```
api/app/
 ├── routers/
 ├── services/
 ├── guardrails/
 ├── security/
 ├── ingest/
 ├── rag/

data/
 ├── contracts/
 ├── seed/

docs/
tests/
```

---

## Security Model

### Authentication

JWT tokens required.

### Authorization

Role based:

* admin → full access
* analyst → AI + search allowed
* viewer → read metadata only

### Tenant Isolation

Every contract belongs to an organization.

All retrieval queries filter by:

```
organization_id
```

---

## Known Limitations

* Clause extraction uses semantic heuristics (not structured parsing)
* Expiry detection assumes 1-year term if missing
* Compare tool may be slow depending on model size
* No streaming responses

---

## Technology Stack

* FastAPI
* Python
* Qdrant
* Ollama
* Docker
* JSON-RPC 2.0

---

## Purpose

This project demonstrates:

* Secure enterprise RAG architecture
* MCP protocol implementation
* LLM guardrail integration
* Multi-tenant contract intelligence backend

---