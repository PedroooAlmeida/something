"""Prompt evaluation.

Two paths:
1. Remote: if GORDON_ENGINE_URL is set, forward the capture event to Person 3's
   intelligence engine and use its response.
2. Mock: a rule-based fallback so the full pipeline (capture -> score -> overlay ->
   dashboard -> buzzer) works end-to-end before the real engine exists, and as a
   fallback when the engine is down (PRD final hour: "handling API failure").

Both return the shared evaluation format from PRD section 17.
"""
import json
import os
import re
import urllib.request

from . import db

ENGINE_URL = os.environ.get("GORDON_ENGINE_URL", "")
ENGINE_TIMEOUT = float(os.environ.get("GORDON_ENGINE_TIMEOUT", "8"))

CATEGORIES = [
    "prompt_specificity",
    "token_conservation",
    "frontier_awareness",
    "tool_selection",
    "context_management",
    "verification",
]

ERROR_MARKERS = re.compile(r"(?i)(error|exception|traceback|stack ?trace|\b4\d\d\b|\b5\d\d\b|failed|undefined|null pointer|segfault)")
FILE_MARKERS = re.compile(r"\b[\w./-]+\.(ts|tsx|js|jsx|py|go|rs|java|rb|css|html|json|yml|yaml|sql|sh)\b")
EXPECTATION_MARKERS = re.compile(r"(?i)(should|expected|instead of|so that|the goal|must|needs to|want it to)")
CONSTRAINT_MARKERS = re.compile(r"(?i)(without|don't|do not|keep|only|limit|constraint|existing api|backward)")
ATTEMPT_MARKERS = re.compile(r"(?i)(i tried|i've tried|already tried|attempted|so far i)")
VERIFY_MARKERS = re.compile(r"(?i)(test|verify|check|assert|run it|source|cite|explain why)")
VAGUE_PROMPTS = re.compile(r"(?i)^(fix (this|it|the code)|make (this|it) work|build me an app|help|do it|it's broken|doesn't work)[.!?]*$")


def _clamp(n: int) -> int:
    return max(0, min(100, n))


def _score_specificity(p: str) -> int:
    words = len(p.split())
    score = 20
    if words >= 8:
        score += 15
    if words >= 20:
        score += 10
    if ERROR_MARKERS.search(p):
        score += 20
    if FILE_MARKERS.search(p):
        score += 15
    if EXPECTATION_MARKERS.search(p):
        score += 10
    if CONSTRAINT_MARKERS.search(p):
        score += 5
    if ATTEMPT_MARKERS.search(p):
        score += 5
    if VAGUE_PROMPTS.match(p.strip()):
        score = min(score, 10)
    return _clamp(score)


def _score_token_conservation(p: str) -> int:
    words = len(p.split())
    score = 90
    if words > 400:
        score -= 20
    if words > 800:
        score -= 25
    if words > 2000:
        score -= 25
    # repeated-context check: duplicated sentences or long lines anywhere in the prompt
    chunks = [c.strip() for c in re.split(r"[.!?\n]+", p) if len(c.strip()) > 30]
    if chunks:
        dup_ratio = 1 - len(set(chunks)) / len(chunks)
        if dup_ratio > 0.5:
            score -= 40
        elif dup_ratio > 0.2:
            score -= 20
    return _clamp(score)


def _score_frontier(p: str, model: str) -> tuple[int, dict | None]:
    """Check prompt + selected model against the knowledge DB's previous_option column."""
    haystack = f"{p} {model}".lower()
    hits = db.rows("SELECT * FROM knowledge_updates WHERE previous_option IS NOT NULL")
    for h in hits:
        prev = (h.get("previous_option") or "").lower()
        if prev and prev in haystack:
            return 25, h
    return 85, None


def _score_tool_selection(p: str) -> int:
    score = 80
    if re.search(r"(?i)(latest|current|today|this week|recently released|newest)", p) and not re.search(r"(?i)(search|look up|browse)", p):
        score -= 25  # needs current info but didn't ask for search
    if re.search(r"(?i)(guess|just try|probably)", p):
        score -= 15
    return _clamp(score)


def _score_context(p: str) -> int:
    words = len(p.split())
    score = 75
    if words < 8:
        score -= 30          # almost certainly missing project context
    if words > 2000:
        score -= 25          # almost certainly includes unrelated context
    return _clamp(score)


def _score_verification(p: str) -> int:
    return 75 if VERIFY_MARKERS.search(p) else 35


ROASTS = {
    "prompt_specificity": [
        "\"{prompt}\"? Six words, no error, no file, no expected result. Even the model is embarrassed for you.",
        "You've given the model less information than a fortune cookie. What is it supposed to do, smell the stack trace?",
    ],
    "token_conservation": [
        "You have pasted the company's founding story, three meeting transcripts, and somebody's lunch order. None of this explains the bug.",
        "That's {words} words of context for a one-line question. The model charges by the token, not by the drama.",
    ],
    "frontier_awareness": [
        "You're reaching for {prev} like it's still {year}. {new} exists. It was released {date}. Read a changelog.",
    ],
    "tool_selection": [
        "You're asking a chat model to guess at current information. That's what search is for. Use the right knife.",
    ],
    "context_management": [
        "The model knows nothing about your project and you've told it even less. It's not psychic, it's autocomplete with ambition.",
    ],
    "verification": [
        "You're about to paste generated code straight into production without running it. Bold. Stupid, but bold.",
    ],
}

DIAGNOSES = {
    "prompt_specificity": "The prompt does not include the actual task, relevant files, the error message, or the expected behavior.",
    "token_conservation": "The prompt repeats or includes large amounts of context that is unrelated to the actual question.",
    "frontier_awareness": "The prompt or selected model relies on an option that has been superseded by a newer release.",
    "tool_selection": "The task needs a different tool than the one being used (e.g. search for current info, a terminal for facts).",
    "context_management": "The model is missing the project context it needs (or is drowning in context it doesn't).",
    "verification": "The prompt does not ask for tests, verification steps, or any way to confirm the output actually works.",
}

LESSONS = {
    "prompt_specificity": "State the file, the exact error, what you expected, and what you already tried. Specific in, specific out.",
    "token_conservation": "Trim the context to what explains the problem. Continue the conversation instead of restarting it.",
    "frontier_awareness": "Check the release notes before picking a model or library. Newer options often remove the workaround you're building.",
    "tool_selection": "Match the tool to the task: search for current facts, a terminal for ground truth, a small model for small jobs.",
    "context_management": "Give the model the minimum context that makes the task unambiguous: project type, relevant file, and the goal.",
    "verification": "End prompts with a verification step: 'write a test that reproduces this' or 'explain how to confirm the fix.'",
}


def _improved_prompt(p: str, category: str) -> str:
    base = p.strip().rstrip(".!?")
    if category == "prompt_specificity":
        return (f"In <file>, <function> fails with <exact error> when <trigger>. "
                f"Expected: <expected behavior>. I already tried <attempt>. "
                f"Find the cause, explain it, and fix it without changing the public API. (Original ask: \"{base}\")")
    if category == "token_conservation":
        return ("Here is the failing function and the exact error only: <paste minimal snippet + error>. "
                "Diagnose and fix just this — ignore the rest of the codebase.")
    if category == "frontier_awareness":
        return f"{base} — use the current release (check the linked release note) rather than the older option."
    if category == "verification":
        return f"{base}. Then write a test that reproduces the bug and confirm it passes after the fix."
    return f"{base}. Context: <project type>, relevant file: <file>, goal: <expected outcome>."


def _severity_and_action(overall: int) -> tuple[int, str]:
    # action union per overlay contract: none | smart_light | desk_buzzer | bell_bot
    if overall >= 75:
        return 0, "none"
    if overall >= 55:
        return 1, "smart_light"
    if overall >= 35:
        return 2, "desk_buzzer"
    return 3, "bell_bot"


def mock_evaluate(event: dict) -> dict:
    p = event.get("prompt_text", "") or ""
    model = event.get("selected_model", "") or ""
    frontier_score, frontier_hit = _score_frontier(p, model)

    scores = {
        "prompt_specificity": _score_specificity(p),
        "token_conservation": _score_token_conservation(p),
        "frontier_awareness": frontier_score,
        "tool_selection": _score_tool_selection(p),
        "context_management": _score_context(p),
        "verification": _score_verification(p),
    }
    primary = min(scores, key=scores.get)
    # overall leans toward the worst category — one bad habit should hurt
    overall = _clamp(int(0.55 * scores[primary] + 0.45 * (sum(scores.values()) / len(scores))))
    severity, action = _severity_and_action(overall)

    if severity == 0:
        # good prompt: no roast, grudging chef approval instead
        return {
            "overall_score": overall,
            "primary_category": primary,
            "category_scores": scores,
            "roast": "Hm. File, error, expected behavior, a constraint, AND a test? Fine. FINE. That's how it's done. Don't let it go to your head.",
            "diagnosis": "No violation — the prompt includes the task, context, and a verification step.",
            "lesson": "Keep doing exactly this.",
            "improved_prompt": p,
            "severity": 0,
            "action": "none",
            "source": None,
        }

    words = len(p.split())
    roast_template = ROASTS[primary][words % len(ROASTS[primary])]
    source = None
    if primary == "frontier_awareness" and frontier_hit:
        roast = roast_template.format(
            prev=frontier_hit.get("previous_option") or "that",
            new=frontier_hit.get("new_option") or "a newer option",
            date=frontier_hit.get("release_date") or "recently",
            year="2023",
        )
        diagnosis = (f"{DIAGNOSES[primary]} {frontier_hit.get('previous_option')} -> "
                     f"{frontier_hit.get('new_option')}.")
        # structured source for the overlay's Frontier Knowledge card —
        # it never renders a claim without source + date
        source = {
            "text": frontier_hit.get("what_changed") or "",
            "date": frontier_hit.get("release_date") or "",
            "confidence": frontier_hit.get("confidence") or "unverified",
            "url": frontier_hit.get("source") or "",
        }
    else:
        roast = roast_template.format(prompt=p[:60], words=words)
        diagnosis = DIAGNOSES[primary]

    return {
        "source": source,
        "overall_score": overall,
        "primary_category": primary,
        "category_scores": scores,
        "roast": roast,
        "diagnosis": diagnosis,
        "lesson": LESSONS[primary],
        "improved_prompt": _improved_prompt(p, primary),
        "severity": severity,
        "action": action,
    }


def evaluate(event: dict) -> tuple[dict, str]:
    """Returns (evaluation, engine_name). Tries the remote engine, falls back to mock."""
    if ENGINE_URL:
        try:
            req = urllib.request.Request(
                ENGINE_URL,
                data=json.dumps(event).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=ENGINE_TIMEOUT) as resp:
                return json.loads(resp.read().decode()), "remote"
        except Exception as exc:  # engine down mid-demo -> keep the show running
            print(f"[evaluator] remote engine failed ({exc}); using mock fallback")
    return mock_evaluate(event), "mock"
