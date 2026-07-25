"""Env vars, constants, paths. All tunable numbers live here."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
AUDIO_CACHE_DIR = PROJECT_ROOT / "audio_cache"
RELEASES_PATH = DATA_DIR / "releases.json"
FIXTURES_PATH = PROJECT_ROOT / "tests" / "fixtures" / "prompts.json"


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader — no dependency. Real env vars win over file values.
    Handles `export KEY=...` prefixes and trailing `# comments`; never crashes boot."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if value and value[0] in "'\"":
            value = value[1:].split(value[0], 1)[0]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(PROJECT_ROOT / ".env")

# --- keys and model selection (read at import; call refresh() after env changes) ---
ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
ELEVENLABS_API_KEY: str = os.environ.get("ELEVENLABS_API_KEY", "")
VOICE_CHEF: str = os.environ.get("VOICE_CHEF", "")
VOICE_PROF: str = os.environ.get("VOICE_PROF", "")
EVAL_MODEL: str = os.environ.get("EVAL_MODEL", "claude-opus-5")

# --- evaluation tunables ---
# claude-opus-5 rejects sampling params (temperature 400s), so the spec's
# "temperature ~0.9 for joke variance" is enforced by prompt in rubric.py instead.
EVAL_EFFORT = "low"  # latency: roast must stream fast (invariant 1)
EVAL_MAX_TOKENS = 2000  # roast+prose+improved_prompt; 1024 truncated long rewrites
SEVERITY_BANDS = (30, 60)  # overall_score < 30 -> severity 3, < 60 -> 2, else 1
EVAL_TIMEOUT_S = 30.0
MAX_ROAST_WORDS = 35
MAX_ROAST_SENTENCES = 2
SHOULD_INTERRUPT_MAX_SCORE = 60  # engine-side backstop; model also decides
GOOD_PROMPT_MIN_SCORE = 80

CATEGORIES: tuple[str, ...] = (
    "prompt_specificity",
    "token_conservation",
    "frontier_awareness",
    "tool_selection",
    "context_management",
    "verification",
)

# --- voice tunables ---
ELEVENLABS_BASE_URL = "https://api.elevenlabs.io"
ELEVENLABS_MODEL_ID = "eleven_flash_v2_5"  # low-latency Flash tier; verify against docs (M1)
ELEVENLABS_OUTPUT_FORMAT = "mp3_44100_128"
ELEVENLABS_TIMEOUT_S = 20.0
ELEVENLABS_MAX_CONCURRENCY = 2  # free tier allows 2 concurrent streams
AUDIO_READY_POLL_S = 0.1  # /audio/{key} wait granularity while synthesis in flight
AUDIO_READY_TIMEOUT_S = 10.0

# --- engine behavior ---
LLM_ATTEMPTS = 2  # one retry on unparseable model output
SYNTH_DEFAULT_SEVERITY = 2  # severity streams in AFTER the roast; synth can't wait for it
SAFE_FALLBACK_ROAST = "That prompt needs work. Let's fix it."  # spoken if safety empties the roast
ACTION_BY_SEVERITY: dict[int, str] = {1: "toast", 2: "desk_buzzer", 3: "desk_buzzer"}

# --- knowledge ---
KNOWLEDGE_MAX_MATCHES = 3

# --- input hardening ---
MAX_SCREENSHOT_BYTES = 8_000_000  # skip larger; also bounds the sync read
MAX_PROMPT_CHARS = 30_000  # truncate giant pastes (still roastable) past this
AUDIO_KEY_LENGTH = 24  # sha256 hex prefix used for cache keys and /audio/{key}

# --- classifier ---
CLASSIFIER_MAX_TOKENS = 200
CLASSIFIER_MIN_PROMPT_CHARS = 2

# --- harness ---
HARNESS_CONCURRENCY = 8


def refresh() -> None:
    """Re-read env-derived settings (used by tests and the M7 fallback drill)."""
    global ANTHROPIC_API_KEY, ELEVENLABS_API_KEY, VOICE_CHEF, VOICE_PROF, EVAL_MODEL
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
    ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
    VOICE_CHEF = os.environ.get("VOICE_CHEF", "")
    VOICE_PROF = os.environ.get("VOICE_PROF", "")
    EVAL_MODEL = os.environ.get("EVAL_MODEL", "claude-opus-5")


def health_status() -> dict[str, object]:
    """Config status for GET /health — never leaks key material."""
    return {
        "anthropic_key": bool(ANTHROPIC_API_KEY),
        "elevenlabs_key": bool(ELEVENLABS_API_KEY),
        "voice_chef": bool(VOICE_CHEF),
        "voice_prof": bool(VOICE_PROF),
        "eval_model": EVAL_MODEL,
        "audio_cache_dir": str(AUDIO_CACHE_DIR),
    }
