# SECURITY — Contract Intelligence MCP Server

---

# 1. Security Philosophy

The system is designed following a **defense-in-depth approach**.

Security is enforced across:

* authentication
* authorization
* tenant isolation
* LLM guardrails
* file access validation
* retrieval filtering

The goal is to ensure:

* contracts from one organization cannot be accessed by another
* sensitive personal data is never leaked
* LLM outputs remain bounded to verified contract context

---

# 2. Authentication

Users authenticate using JWT tokens.

Each token includes:

* user_id
* organization_id
* role

The token is required for:

* all MCP calls
* contract search
* AI queries
* metadata extraction
* risk scoring

Requests without valid authentication are rejected.

---

# 3. Role-Based Access Control (RBAC)

Roles supported:

* admin
* analyst
* viewer

Restrictions:

* viewer cannot perform semantic search
* viewer cannot invoke AI tools
* viewer cannot run clause comparison
* viewer can only access permitted read-only operations

All tool handlers validate the user role before execution.

---

# 4. Multi-Tenant Isolation

Tenant separation is enforced at multiple levels.

---

## 4.1 Vector Database Isolation

Each vector stored in Qdrant includes:

* organization_id
* contract_id

Every retrieval request includes:

```
organization_id filter
```

This prevents cross-tenant vector access.

---

## 4.2 Database Document Isolation

Before any contract is accessed:

```
require_document_read_access(user, contract_id)
```

This ensures:

* the contract exists
* it belongs to the user's organization

Unauthorized access attempts are rejected.

---

## 4.3 File System Protection

Contract files are stored locally.

Before reading any file:

* database lookup verifies ownership
* path is validated
* file existence is checked

This prevents:

* arbitrary file reads
* path traversal attacks
* unauthorized contract access

---

# 5. LLM Security Controls

Because LLMs may hallucinate or leak sensitive data, strict controls are enforced.

---

## 5.1 Context Restriction

The LLM receives ONLY:

* retrieved contract chunks
* the user question

The LLM is explicitly instructed:

```
Use ONLY the provided context.
If answer not found → respond:
"Not found in the provided contracts."
```

This prevents hallucinated contract answers.

---

## 5.2 Citation Enforcement

The prompt includes an explicit list of allowed citations.

The LLM is instructed:

```
You are ONLY allowed to cite from this list.
```

This prevents fabricated references.

---

# 6. Prompt Injection Protection

Incoming queries are scanned for:

* jailbreak attempts
* system prompt exposure attempts
* malicious instructions

Suspicious prompts are rejected before reaching the LLM.

---

# 7. Input Moderation

User queries are checked for:

* disallowed content
* malicious instructions
* unsafe inputs

Blocked inputs return a validation error.

---

# 8. PII Redaction

Sensitive personal information is protected at both stages.

---

## Input Redaction

Before retrieval:

* emails are detected
* phone numbers detected
* SSN-like patterns detected

These are replaced with safe placeholders.

---

## Output Redaction

After LLM generation:

* output is scanned again
* any detected PII is masked

This prevents accidental leakage from contract text.

---

# 9. Deterministic Tool Design

High-risk operations are implemented without LLM dependency.

These include:

* metadata extraction
* expiry calculation
* risk scoring

Using deterministic logic reduces:

* hallucination risk
* inconsistent outputs
* security uncertainty

---

# 10. Resource Limits

To prevent abuse:

* contract file reads are capped in size
* retrieval returns limited top-K chunks
* LLM prompt size is bounded

This protects against:

* memory exhaustion
* extremely large inputs
* denial-of-service patterns

---

# 11. Why These Controls Matter

Contracts may contain:

* company confidential terms
* personal contact details
* financial obligations
* legal liabilities

The layered protections ensure:

* zero cross-tenant leakage
* bounded AI outputs
* minimal hallucination risk
* safe file access

---

# 12. Production Hardening (Future Work)

Possible future security enhancements:

* audit logs for all MCP tool usage
* rate limiting per organization
* encrypted contract storage
* signed upload verification
* secret rotation support
* structured policy enforcement