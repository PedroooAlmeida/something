"""Banned-term filter + anti-fabrication scrubber.

Runs BEFORE synthesis, always (invariant 3). Full implementation lands in M5;
the API shape is wired from M1 so the engine's call site never changes.
"""

from __future__ import annotations


def filter_text(text: str, context: str) -> tuple[str, list[str]]:
    """Return (safe_text, dropped_notes).

    M5 will implement: banned-term regex + anti-fabrication scrubber (numbers/
    percentages/versions/dates not present in `context` drop their sentence).
    """
    return text, []
