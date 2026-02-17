# Tests (placeholders)

Add tests for:
- RBAC + tenant isolation (403 on cross-org access, viewer upload blocked, etc.)
- Guardrails (PII redaction, injection blocking, citation verification)
- MCP tool access control (403 if user cannot access contract)

Recommended:
- pytest + httpx
- Postman collection for demo
