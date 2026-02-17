# Enterprise Contract Intelligence System (PoC)

This repository is a PoC for:
- Multi-tenant RBAC + tenant isolation
- AI guardrails (PII redaction, prompt-injection blocking, citation verification, toxicity filtering)
- MCP server exposing contract analysis tools
- Self-hosted LLM + vector DB infrastructure

## Quickstart (local)
1. Copy env:
   - `cp .env.example .env`
2. Start services:
   - `docker compose up -d`
3. Run API locally (optional if you prefer container):
   - `cd api && python -m venv .venv && source .venv/bin/activate`
   - `pip install -r requirements.txt`
   - `uvicorn app.main:app --reload --port 8000`

API docs: `http://localhost:8000/docs`

## Repo layout
- `api/` FastAPI app (auth, RBAC, guardrails, RAG)
- `mcp_server/` MCP JSON-RPC server exposing 6 tools
- `infra/` docker compose, configs
- `docs/` architecture + API examples
- `tests/` RBAC + guardrails test cases
- `data/` sample tenant contracts and extracted text (PoC)

## Notes
- This is scaffolding with placeholders. Fill in implementation incrementally.
