"""Text heuristics: vagueness, specificity markers, similarity, OCR cleanup."""
import re

AFFIRMATIONS = {
    "ok", "okay", "yes", "y", "yep", "yeah", "sure", "thanks", "thank you",
    "continue", "go on", "go ahead", "do it", "sounds good", "lgtm",
    "perfect", "great", "nice", "cool", "no", "nope",
}

VAGUE_PATTERNS = [re.compile(p, re.I) for p in [
    r"\bmake (this|it) work\b",
    r"\bfix (this|it|the code)\b",
    r"\b(doesn'?t|does not|not|won'?t) work(ing)?\b",
    r"\bit'?s broken\b",
    r"\bhelp me\b",
    r"\bbuild me\b",
    r"\bmake (it|this) better\b",
    r"\bimprove (this|it)\b",
    r"\boptimi[sz]e this\b",
    r"\bclean (this|it) up\b",
    r"\bwhy (isn'?t|is not) (this|it) working\b",
    r"\bmake an? app\b",
    r"\bdo something\b",
]]

SPEC_MARKERS = [re.compile(p) for p in [
    r"(?i)\b(traceback|error|exception|failed|failure|status \d{3}|[45]\d{2} \w)",
    r"[\w./-]+\.(py|ts|tsx|js|jsx|go|rs|java|rb|cpp|hpp|css|html|json|ya?ml|sql|sh|swift|kt|md)\b",
    r"```|`[^`]+`",
    r":\d+\b",                                            # file:line
    r"(?i)\b(expected|should (return|be|show|print)|instead of|actual (behavior|output))\b",
]]


def normalize(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text).strip().lower()


def is_affirmation(text: str) -> bool:
    return normalize(text) in AFFIRMATIONS


def is_skippable(text: str) -> bool:
    """Not worth a model call: affirmations, tiny replies, pure error pastes
    (pasting an error with no fluff is good behavior, not roastable)."""
    t = text.strip()
    if is_affirmation(t) or len(t) < 12:
        return True
    if (SPEC_MARKERS[0].search(t) and vagueness_hits(t) == 0
            and len(t.split()) > 20 and "?" not in t):
        return True
    return False


def vagueness_hits(text: str) -> int:
    return sum(1 for p in VAGUE_PATTERNS if p.search(text))


def specificity_markers(text: str) -> int:
    return sum(1 for p in SPEC_MARKERS if p.search(text))


def jaccard(a: str, b: str) -> float:
    """Word-set similarity; robust to OCR noise."""
    wa, wb = set(a.lower().split()), set(b.lower().split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


# Model-picker text seen in composer OCR. First matching family wins; the
# demo targets Claude apps, so the claude pattern is checked first.
MODEL_PATTERNS = [
    (re.compile(r"\b(?:claude[\s-]+)?(opus|sonnet|haiku|fable)[\s-]?"
                r"(\d(?:\.\d)?)\b", re.I),
     lambda m: f"claude-{m.group(1).lower()}-{m.group(2)}"),
    (re.compile(r"\bgpt[\s-]?(\d(?:\.\d)?|4o)(?:[\s-](mini|nano|turbo|pro))?\b",
                re.I),
     lambda m: "gpt-" + m.group(1).lower()
               + (f"-{m.group(2).lower()}" if m.group(2) else "")),
    (re.compile(r"\bgemini[\s-]?(\d(?:\.\d)?)(?:[\s-](pro|flash|ultra))?\b",
                re.I),
     lambda m: "gemini-" + m.group(1)
               + (f"-{m.group(2).lower()}" if m.group(2) else "")),
    (re.compile(r"\bgrok[\s-]?(\d(?:\.\d+)?)\b", re.I),
     lambda m: f"grok-{m.group(1)}"),
    (re.compile(r"\bdeepseek(?:[\s-]?([vr]\d))?\b", re.I),
     lambda m: "deepseek" + (f"-{m.group(1).lower()}" if m.group(1) else "")),
]


def detect_model(text: str) -> str | None:
    """Best-effort model name from OCR text (picker labels like 'Opus 5',
    'GPT-4o mini'). Returns normalized id, or None if nothing recognized."""
    for pattern, norm in MODEL_PATTERNS:
        m = pattern.search(text)
        if m:
            return norm(m)
    return None


def clean_ocr(text: str, placeholders: list) -> str:
    """Drop UI-chrome lines (composer placeholders, send buttons) from OCR output."""
    kept = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        low = s.lower()
        if any(ph in low for ph in placeholders):
            continue
        kept.append(s)
    return "\n".join(kept)
