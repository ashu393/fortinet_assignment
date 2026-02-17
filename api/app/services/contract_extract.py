import re
from datetime import datetime
from typing import Optional, Dict, Any

DATE_PATTERNS = [
    # March 15, 2024
    re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b", re.I),
    # 2024-03-15
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
]

NOTICE_RE = re.compile(r"\b(\d{1,3})\s*\(\s*\d{1,3}\s*\)\s*days\b|\b(\d{1,3})\s*days\b", re.I)
GOV_LAW_RE = re.compile(r"\bgoverned by the laws of\s+([A-Za-z\s,]+)\b", re.I)
TERM_RE = re.compile(r"\bterm\s+of\s+(\d{1,3})\s*(year|years|month|months)\b", re.I)
AUTO_RENEW_RE = re.compile(r"\bauto(?:matically)?\s+renew(?:al|s)?\b|\bauto-renew\b", re.I)

def _parse_date(text: str) -> Optional[str]:
    for pat in DATE_PATTERNS:
        m = pat.search(text)
        if m:
            s = m.group(0)
            # normalize to YYYY-MM-DD if possible
            try:
                if "-" in s:
                    dt = datetime.strptime(s, "%Y-%m-%d")
                else:
                    dt = datetime.strptime(s, "%B %d, %Y")
                return dt.strftime("%Y-%m-%d")
            except Exception:
                return s
    return None

def extract_metadata_from_text(contract_id: str, title: str, text: str) -> Dict[str, Any]:
    effective_date = _parse_date(text)

    # termination notice
    notice_days = None
    nm = NOTICE_RE.search(text)
    if nm:
        notice_days = int(nm.group(1) or nm.group(2))

    # governing law
    gov_law = None
    gm = GOV_LAW_RE.search(text)
    if gm:
        gov_law = gm.group(1).strip()

    # term
    term = None
    tm = TERM_RE.search(text)
    if tm:
        term = f"{tm.group(1)} {tm.group(2)}"

    auto_renew = bool(AUTO_RENEW_RE.search(text))

    return {
        "contract_id": contract_id,
        "title": title,
        "effective_date": effective_date,
        "term": term,
        "auto_renew": auto_renew,
        "termination_notice_days": notice_days,
        "governing_law": gov_law,
    }