"""Capture-side platform asks: model name in events, submit-only gate."""
import json
import os

import pytest

from capture.emitter import Emitter
from capture.machine import SemEvent
from capture.textutil import detect_model
from capture.triggers import TriggerEngine


# -- detect_model -----------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("Opus 5", "claude-opus-5"),
    ("claude-opus-5", "claude-opus-5"),
    ("Claude Sonnet 4.5 ▾", "claude-sonnet-4.5"),
    ("Haiku 4.5", "claude-haiku-4.5"),
    ("GPT-5", "gpt-5"),
    ("gpt-4o mini", "gpt-4o-mini"),
    ("Gemini 2.5 Pro", "gemini-2.5-pro"),
    ("Grok 4", "grok-4"),
    ("DeepSeek V3", "deepseek-v3"),
    ("fix the login bug in auth.py", None),
    ("", None),
])
def test_detect_model(text, expected):
    assert detect_model(text) == expected


def test_detect_model_prefers_claude_over_other_families():
    assert detect_model("GPT-5  |  Opus 5") == "claude-opus-5"


# -- emitter carries selected_model -----------------------------------------

def test_emitter_stamps_selected_model(tmp_path):
    em = Emitter(str(tmp_path))
    em.selected_model = "claude-opus-5"
    path = em.write({"kind": "submission", "ts": 1000.0, "evidence": "x"})
    with open(path) as f:
        event = json.load(f)
    assert event["selected_model"] == "claude-opus-5"


def test_emitter_defaults_selected_model_unknown(tmp_path):
    em = Emitter(str(tmp_path))
    path = em.write({"kind": "submission", "ts": 1000.0, "evidence": "x"})
    with open(path) as f:
        assert json.load(f)["selected_model"] == "unknown"


# -- submit-only gate --------------------------------------------------------

class _Cfg:
    submit_only = True
    model_enabled = False
    model_timeout_s = 10.0
    model_score_threshold = 55
    model_confidence_min = 0.6
    model_max_text = 1500
    anthropic_model = "claude-opus-5"
    cooldown_s = 0.0
    kind_cooldown_s = 0.0
    token_dump_min = 2000
    token_dump_severe = 6000
    no_read_ms = 8000
    no_read_response_len = 1200
    lazy_dwell_ms = 2000
    lazy_len = 40
    repeat_similarity = 0.85
    thrash_count = 3
    thrash_window_s = 90.0
    thrash_similarity = 0.5


class _SpyEmitter:
    def __init__(self):
        self.events = []

    def write(self, event):
        self.events.append(event)
        return "spy"


def _engine(submit_only=True):
    cfg = _Cfg()
    cfg.submit_only = submit_only
    return cfg, TriggerEngine(cfg, _SpyEmitter())


def test_submit_only_drops_paste_and_reading_sems():
    _, eng = _engine()
    paste = SemEvent("paste", 1.0, {"size": 9999})
    read = SemEvent("reading_ended", 2.0, {
        "read_time_ms": 100, "response_len": 5000, "scrolled": False})
    assert eng.process(paste) is None
    assert eng.process(read) is None
    assert eng.emitter.events == []


def test_submit_only_still_fires_on_submission():
    _, eng = _engine()
    sem = SemEvent("submission", 1.0, {
        "text": "fix this", "submits_in_window": 0, "recent_texts": [],
        "similarity_to_prev": 0.0, "dwell_ms": 100})
    assert eng.process(sem) is not None
    assert eng.emitter.events[0]["kind"] == "lazy_prompt"


def test_gate_off_keeps_paste_events():
    _, eng = _engine(submit_only=False)
    paste = SemEvent("paste", 1.0, {"size": 9999})
    assert eng.process(paste) is not None
    assert eng.emitter.events[0]["kind"] == "token_dump"
