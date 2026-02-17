from app.guardrails.input import redact_pii

def scan_output_pii(text: str) -> tuple[str, dict]:
    return redact_pii(text)

def verify_citations(answer: str, user_id: str, org_id: str) -> tuple[str, list]:
    # Minimal PoC: if require citations later, enforce in prompt.
    # For now, we just return no issues.
    return answer, []

def toxicity_filter(text: str, threshold: float = 0.7) -> tuple[bool, str | None]:
    return True, None