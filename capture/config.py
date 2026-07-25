"""Config with defaults, optionally overridden by config.json at repo root."""
import json
import os
from dataclasses import dataclass, field, fields


@dataclass
class Config:
    # Which apps Gordon is allowed to watch. Anything else: no capture at all.
    allowlist: list = field(default_factory=lambda: [
        "Google Chrome", "Safari", "Arc", "Claude", "ChatGPT",
        "Cursor", "Code", "Visual Studio Code", "Terminal", "iTerm2",
    ])
    events_dir: str = "roast_events"
    fps: float = 10.0

    # Grid change detection (frame downscaled to 320x192, 8x6 cells)
    cell_diff_threshold: float = 4.0     # mean abs gray delta per cell
    scroll_cell_fraction: float = 0.6    # >= this fraction of cells changed => scroll
    composer_y0: float = 0.70            # rows below this fraction = composer region

    # OCR crop bands as (x0, y0, x1, y1) fractions of the window
    composer_band: tuple = (0.05, 0.72, 0.95, 0.98)
    conversation_band: tuple = (0.05, 0.10, 0.95, 0.70)
    ocr_min_interval_s: float = 0.4

    # OCR lines that are UI chrome, not user text
    placeholders: list = field(default_factory=lambda: [
        "reply to claude", "ask anything", "message chatgpt", "how can i help",
        "send a message", "type a message", "write a message",
    ])

    # State machine
    paste_delta: int = 200               # chars appearing in one tick => paste
    submit_corroborate_s: float = 1.5    # window for new-block corroboration
    stream_settle_s: float = 1.5         # conversation static this long => DONE

    # Triggers
    token_dump_min: int = 2000
    token_dump_severe: int = 6000
    no_read_ms: int = 8000
    no_read_response_len: int = 1200
    lazy_dwell_ms: int = 2000
    lazy_len: int = 40
    repeat_similarity: float = 0.85
    thrash_count: int = 3
    thrash_window_s: float = 90.0
    thrash_similarity: float = 0.5

    # Gate
    cooldown_s: float = 45.0             # global min gap between fired events
    kind_cooldown_s: float = 600.0       # per-kind gap, unless escalating
    # Demo/privacy mode per PRD: only submission-triggered events fire
    # (paste/reading_ended sems are dropped). CLI: --submit-only.
    submit_only: bool = False

    # Model classifier (Anthropic; key from ANTHROPIC_API_KEY in env or .env)
    model_enabled: bool = True
    anthropic_model: str = "claude-opus-5"
    model_timeout_s: float = 10.0
    model_score_threshold: int = 55      # fire when score below this...
    model_confidence_min: float = 0.6    # ...and confidence above this
    model_max_text: int = 1500           # prompt chars sent to the model

    # Live activity feed (capture/live.py)
    summary_interval_s: float = 8.0      # min gap between Claude summaries
    live_max_text: int = 6000            # screen OCR chars sent to Claude


def load(path: str = "config.json") -> Config:
    cfg = Config()
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
        valid = {f.name for f in fields(Config)}
        for k, v in data.items():
            if k in valid:
                setattr(cfg, k, tuple(v) if isinstance(getattr(cfg, k), tuple) else v)
    return cfg
