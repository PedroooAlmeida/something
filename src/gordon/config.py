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
    """Minimal .env loader — no dependency. Real env vars win over file values."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(PROJECT_ROOT / ".env")

# --- keys and model selection (read at import; call refresh() after env changes) ---
OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
ELEVENLABS_API_KEY: str = os.environ.get("ELEVENLABS_API_KEY", "")
VOICE_CHEF: str = os.environ.get("VOICE_CHEF", "")
VOICE_PROF: str = os.environ.get("VOICE_PROF", "")
EVAL_MODEL: str = os.environ.get("EVAL_MODEL", "gpt-4.1-mini")

# --- evaluation tunables ---
EVAL_TEMPERATURE = 0.9  # jokes need variance (M3 spec)
EVAL_MAX_TOKENS = 900
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
AUDIO_READY_POLL_S = 0.1  # /audio/{key} wait granularity while synthesis in flight
AUDIO_READY_TIMEOUT_S = 10.0

# --- knowledge ---
KNOWLEDGE_MAX_MATCHES = 3


def refresh() -> None:
    """Re-read env-derived settings (used by tests and the M7 fallback drill)."""
    global OPENAI_API_KEY, ELEVENLABS_API_KEY, VOICE_CHEF, VOICE_PROF, EVAL_MODEL
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
    VOICE_CHEF = os.environ.get("VOICE_CHEF", "")
    VOICE_PROF = os.environ.get("VOICE_PROF", "")
    EVAL_MODEL = os.environ.get("EVAL_MODEL", "gpt-4.1-mini")


def health_status() -> dict[str, object]:
    """Config status for GET /health — never leaks key material."""
    return {
        "openai_key": bool(OPENAI_API_KEY),
        "elevenlabs_key": bool(ELEVENLABS_API_KEY),
        "voice_chef": bool(VOICE_CHEF),
        "voice_prof": bool(VOICE_PROF),
        "eval_model": EVAL_MODEL,
        "audio_cache_dir": str(AUDIO_CACHE_DIR),
    }
