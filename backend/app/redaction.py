"""Privacy redaction (PRD section 22): strip secrets/PII before storing or forwarding."""
import re

PATTERNS: list[tuple[str, re.Pattern]] = [
    ("api_key", re.compile(r"\b(sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|xox[bap]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{30,})\b")),
    ("bearer_token", re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._-]{16,}")),
    ("password_assignment", re.compile(r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key)\s*[:=]\s*\S+")),
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("credit_card", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
]


def redact(text: str | None) -> tuple[str, list[str]]:
    """Returns (redacted_text, list of redaction kinds applied)."""
    if not text:
        return "", []
    applied = []
    for kind, pattern in PATTERNS:
        if pattern.search(text):
            applied.append(kind)
            if kind == "bearer_token":
                text = pattern.sub(r"\1[REDACTED]", text)
            elif kind == "password_assignment":
                text = pattern.sub(lambda m: re.split(r"[:=]", m.group(0), maxsplit=1)[0] + ": [REDACTED]", text)
            else:
                text = pattern.sub(f"[REDACTED_{kind.upper()}]", text)
    return text, applied
