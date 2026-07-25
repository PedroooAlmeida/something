"""Secret detection + redaction. Runs before any text is stored."""
import re

# Order matters: sk-ant- must match before the generic sk- pattern.
PATTERNS = [
    ("anthropic_key", re.compile(r"sk-ant-[A-Za-z0-9_-]{16,}")),
    ("openai_key", re.compile(r"sk-[A-Za-z0-9_-]{20,}")),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36}")),
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("db_url", re.compile(r"(?i)\b(postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://\S+")),
    ("credential_assignment",
     re.compile(r"(?i)\b(password|passwd|secret|api[_-]?key|access[_-]?token)\b\s*[:=]\s*['\"]?\S{6,}")),
]


def find_secrets(text: str) -> list:
    """Return labels of secret types present in text. Matches are masked as
    they're found so one secret can't count as two types (sk-ant- is also
    a valid match for the generic sk- pattern)."""
    found = []
    for name, pat in PATTERNS:
        if pat.search(text):
            found.append(name)
            text = pat.sub("", text)
    return found


def redact(text: str) -> str:
    for name, pat in PATTERNS:
        text = pat.sub(f"[{name.upper()}]", text)
    return text
