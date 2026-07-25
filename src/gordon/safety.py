"""Banned-term filter + anti-fabrication scrubber.

Runs BEFORE synthesis, always (invariant 3). Regexes are allowed here — the
no-regex rule applies to engine.py only.

Layer 1 — banned terms. This is a backstop to the rubric rule "attack the
decision, never the person" (invariant 6), not a slur lexicon (deliberately not
vendored into a public hackathon repo). Covers person-directed intelligence
insults, appearance insults, identity mentions (any identity content in a roast
is off-mission, so the whole sentence goes), and profanity beyond persona spice
("damn"/"hell"/"bloody" stay — it's a chef).

Layer 2 — anti-fabrication (invariant 4). Every number, percentage, version
string, or date in the text must appear in the supplied context (the captured
prompt + injected knowledge records), or its sentence is dropped and logged.
"""

from __future__ import annotations

import re

from gordon import config

_BANNED_TERMS = (
    # person-directed intelligence-as-trait
    "idiot", "idiots", "moron", "morons", "imbecile", "imbeciles", "dumbass",
    "dimwit", "halfwit", "brainless", "braindead", "retard", "retarded",
    # appearance
    "ugly", "fat", "hideous",
    # profanity beyond persona spice
    "fuck", "fucking", "fucked", "shit", "shitty", "bullshit", "asshole",
    "bastard", "bitch", "cunt", "prick", "whore", "slut",
    # identity terms — a roast has no business mentioning identity at all
    "gay", "lesbian", "trans", "transgender", "jew", "jewish", "muslim",
    "christian", "hindu", "buddhist", "black", "white", "asian", "latino",
    "immigrant", "disabled", "autistic",
)
_BANNED_RE = re.compile(r"\b(?:" + "|".join(_BANNED_TERMS) + r")\b", re.IGNORECASE)

# "you're stupid" attacks the person; "this stupid prompt" attacks the artifact.
_PERSON_DIRECTED_RE = re.compile(
    r"\b(?:you(?:'re| are| were| look| sound| seem)?|they(?:'re| are)?|he(?:'s| is)?|she(?:'s| is)?)"
    r"\s+(?:so\s+|such\s+an?\s+|too\s+)?(?:stupid|dumb|thick|dense|clueless|useless)\b",
    re.IGNORECASE,
)

# Candidate "facts": percentages, versions (v2.0 / 3.14.1), 4-digit years,
# month-name dates, then bare numbers. Order matters — first match wins per span.
_FACT_RE = re.compile(
    r"""
    \d+(?:\.\d+)?\s*%                                             # 40%
  | \bv?\d+(?:\.\d+)+\b                                           # v2.1 / 3.14.0
  | \b(?:19|20)\d{2}-\d{2}-\d{2}\b                                # 2025-10-07
  | \b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(?:,?\s*(?:19|20)\d{2})?
  | \b(?:19|20)\d{2}\b                                            # bare year
  | \b\d+(?:\.\d+)?\b                                             # bare number
    """,
    re.IGNORECASE | re.VERBOSE,
)

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _normalize(token: str) -> str:
    return token.lower().lstrip("v").replace(",", "").replace(" ", "").rstrip(".")


def fact_tokens(text: str) -> list[str]:
    """All number/percentage/version/date tokens in the text."""
    return [m.group(0) for m in _FACT_RE.finditer(text)]


def _unsupported_facts(sentence: str, normalized_context: str) -> list[str]:
    return [
        token
        for token in fact_tokens(sentence)
        if _normalize(token) not in normalized_context
    ]


def filter_text(text: str, context: str) -> tuple[str, list[str]]:
    """Return (safe_text, dropped_notes). A sentence is dropped if it contains a
    banned term, a person-directed insult, or a fact absent from the context."""
    normalized_context = _normalize(context)
    kept: list[str] = []
    dropped: list[str] = []
    for sentence in _SENTENCE_SPLIT_RE.split(text.strip()):
        if not sentence:
            continue
        if match := _BANNED_RE.search(sentence):
            dropped.append(f"banned term {match.group(0)!r} in: {sentence[:80]!r}")
            continue
        if match := _PERSON_DIRECTED_RE.search(sentence):
            dropped.append(f"person-directed {match.group(0)!r} in: {sentence[:80]!r}")
            continue
        if unsupported := _unsupported_facts(sentence, normalized_context):
            dropped.append(f"fabricated {unsupported!r} in: {sentence[:80]!r}")
            continue
        kept.append(sentence)
    return " ".join(kept), dropped


def detect_fabrications(text: str, context: str) -> list[str]:
    """Log-only variant for improved_prompt — stripping sentences from a rewritten
    prompt would break it, so fabrications are reported, not removed."""
    normalized_context = _normalize(context)
    return [
        f"fabricated {tokens!r} in: {sentence[:80]!r}"
        for sentence in _SENTENCE_SPLIT_RE.split(text.strip())
        if sentence and (tokens := _unsupported_facts(sentence, normalized_context))
    ]


def enforce_roast_budget(text: str) -> str:
    """Hard cap: <= MAX_ROAST_SENTENCES sentences and <= MAX_ROAST_WORDS words
    (invariant 5 — it is spoken aloud). Drops trailing sentences first, then
    hard-truncates words as the last resort."""
    sentences = [s for s in _SENTENCE_SPLIT_RE.split(text.strip()) if s]
    sentences = sentences[: config.MAX_ROAST_SENTENCES]
    while len(sentences) > 1 and sum(len(s.split()) for s in sentences) > config.MAX_ROAST_WORDS:
        sentences.pop()
    result = " ".join(sentences)
    words = result.split()
    if len(words) > config.MAX_ROAST_WORDS:
        result = " ".join(words[: config.MAX_ROAST_WORDS]).rstrip(",;:") + "."
    return result
