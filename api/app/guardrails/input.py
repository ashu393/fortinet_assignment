import re

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
PHONE_RE = re.compile(r"\b(\+?\d{1,2}[\s-]?)?(\(?\d{3}\)?[\s-]?)\d{3}[\s-]?\d{4}\b")

INJECTION_PATTERNS = [
    "ignore previous instructions",
    "disregard previous instructions",
    "system prompt",
    "you are now",
    "developer message",
    "reveal hidden",
    "bypass",
    "jailbreak",
]

def redact_pii(text: str) -> tuple[str, dict]:
    meta = {"emails": 0, "ssn": 0, "phones": 0}

    def _sub(regex, repl_key, repl):
        nonlocal text
        matches = list(regex.finditer(text))
        meta[repl_key] += len(matches)
        text = regex.sub(repl, text)

    _sub(EMAIL_RE, "emails", "[EMAIL_REDACTED]")
    _sub(SSN_RE, "ssn", "[SSN_REDACTED]")
    _sub(PHONE_RE, "phones", "[PHONE_REDACTED]")

    return text, meta

def detect_prompt_injection(text: str) -> bool:
    t = text.lower()
    return any(p in t for p in INJECTION_PATTERNS)

def moderate_input(text: str) -> tuple[bool, str | None]:
    # Minimal PoC: allow all
    return True, None