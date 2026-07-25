"""Roastworthiness classifier — pre-gate before the full roast pipeline.

Heuristic fast path first (empty/garbage/credential-looking captures never hit
the model), then an LLM verdict via the same stream_llm seam as the engine.
"""

from __future__ import annotations

import re

from pydantic import ValidationError

from gordon import config, llm, parsing, rubric
from gordon.schemas import CaptureEvent, ClassifierVerdict

# Anything that smells like a secret is never roasted (and never echoed back).
_SECRET_RE = re.compile(
    r"""
    \bsk-[A-Za-z0-9_-]{16,}            # OpenAI/Anthropic-style keys
  | \bgh[pousr]_[A-Za-z0-9]{20,}       # GitHub tokens
  | \bxox[baprs]-[A-Za-z0-9-]{10,}     # Slack tokens
  | \bAKIA[0-9A-Z]{16}\b               # AWS access keys
  | \b(?:password|passwd|secret|api[_-]?key|token)\s*[:=]\s*\S+
  | -----BEGIN\s+(?:RSA|EC|OPENSSH|PGP)?\s*PRIVATE\s+KEY
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _heuristic(event: CaptureEvent) -> ClassifierVerdict | None:
    """Cheap verdicts that need no model call; None means 'ask the model'."""
    text = event.prompt_text.strip()
    if not text:
        return ClassifierVerdict(
            roastworthy=False, confidence=1.0, reason="Empty capture — nothing was typed."
        )
    if len(text) < config.CLASSIFIER_MIN_PROMPT_CHARS:
        return ClassifierVerdict(
            roastworthy=False,
            confidence=0.9,
            reason="Too short to be a judgeable prompt — likely mid-typing.",
        )
    if _SECRET_RE.search(text):
        return ClassifierVerdict(
            roastworthy=False,
            confidence=1.0,
            reason="Capture appears to contain credentials or secrets — never roasted.",
        )
    return None


async def classify(event: CaptureEvent) -> ClassifierVerdict:
    if verdict := _heuristic(event):
        print(f"[classifier] event={event.event_id} heuristic: {verdict.reason}")
        return verdict

    chunks: list[str] = []
    async for chunk in llm.stream_llm(
        rubric.build_classifier_prompt(event), max_tokens=config.CLASSIFIER_MAX_TOKENS
    ):
        chunks.append(chunk)
    try:
        verdict = ClassifierVerdict.model_validate(parsing.recover_json("".join(chunks)))
    except (ValueError, ValidationError) as exc:
        # A broken classifier must not block the pipeline — default to roastworthy
        # and let the full evaluation (with its own retry) decide.
        print(f"[classifier] event={event.event_id} unparseable verdict, defaulting: {exc}")
        verdict = ClassifierVerdict(
            roastworthy=True, confidence=0.3, reason="Classifier output unparseable; deferred to full evaluation."
        )
    print(
        f"[classifier] event={event.event_id} roastworthy={verdict.roastworthy} "
        f"confidence={verdict.confidence:.2f} hint={verdict.category_hint} — {verdict.reason}"
    )
    return verdict
