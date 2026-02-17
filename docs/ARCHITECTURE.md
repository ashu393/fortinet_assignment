# Architecture (PoC)

## Components
- FastAPI API: auth/JWT, RBAC, tenant isolation, guardrails, RAG entrypoints
- Vector DB: Qdrant for chunk storage and retrieval
- LLM: Ollama for local inference
- MCP Server: JSON-RPC 2.0 tool server exposing 6 tools for the agent

## Request flow (high level)
1. User -> API (JWT auth)
2. API RBAC + tenant checks
3. Input guardrails (PII redaction, injection detection, moderation)
4. Retrieval + tool calls (via MCP)
5. LLM synthesis (requires citations)
6. Output guardrails (PII scan, citation verification, toxicity)
7. Response
