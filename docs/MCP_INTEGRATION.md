# MCP Integration Guide (placeholder)

## Transport
- HTTP JSON-RPC 2.0

## MCP tools
- search_contracts
- extract_clause
- compare_clauses
- extract_metadata
- calculate_risk_score
- find_expiring_contracts

Each tool request MUST include:
- user_id
- organization_id where applicable

RBAC checks happen inside MCP server before returning any data.
