"""Pydantic models for all boundaries: CaptureEvent, Evaluation, EngineResponse."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from gordon.config import CATEGORIES, SEVERITY_BANDS, SHOULD_INTERRUPT_MAX_SCORE

AudioStatus = Literal["cached", "streaming", "fallback_system_tts", "unavailable"]


class CaptureEvent(BaseModel):
    """Input contract — sent by Person 2's capture extension."""

    event_id: str
    timestamp: str = ""
    source: str = "chat_application"
    application: str = ""
    prompt_text: str
    selected_model: str = "unknown"
    screenshot_path: str | None = None
    session_id: str = ""
    personality_id: str = "angry_chef"


class Evaluation(BaseModel):
    """The model's structured verdict (parsed from the LLM's JSON output)."""

    roast: str
    overall_score: int = Field(ge=0, le=100)
    primary_category: str
    category_scores: dict[str, int]
    diagnosis: str
    lesson: str
    improved_prompt: str
    severity: int = Field(ge=1, le=3)
    should_interrupt: bool

    @model_validator(mode="before")
    @classmethod
    def derive_flags_if_truncated(cls, data: dict) -> dict:
        """A truncated stream can lose trailing keys; severity and should_interrupt
        are deterministic functions of overall_score, so derive rather than die."""
        if isinstance(data, dict) and isinstance(data.get("overall_score"), int):
            score = data["overall_score"]
            if "severity" not in data:
                low, high = SEVERITY_BANDS
                data["severity"] = 3 if score < low else 2 if score < high else 1
            if "should_interrupt" not in data:
                data["should_interrupt"] = score < SHOULD_INTERRUPT_MAX_SCORE
        return data

    @field_validator("category_scores")
    @classmethod
    def all_six_categories(cls, v: dict[str, int]) -> dict[str, int]:
        missing = [c for c in CATEGORIES if c not in v]
        if missing:
            raise ValueError(f"category_scores missing keys: {missing}")
        return {c: max(0, min(100, int(v[c]))) for c in CATEGORIES}

    @field_validator("primary_category")
    @classmethod
    def known_category(cls, v: str) -> str:
        if v not in CATEGORIES:
            raise ValueError(f"unknown primary_category: {v}")
        return v


class ClassifierVerdict(BaseModel):
    """POST /classify output — pre-gate deciding whether an event deserves the
    full roast pipeline."""

    roastworthy: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    category_hint: str | None = None

    @field_validator("category_hint")
    @classmethod
    def known_or_none(cls, v: str | None) -> str | None:
        return v if v in CATEGORIES else None


class SourceCitation(BaseModel):
    """Knowledge-record citation surfaced to Person 4's platform."""

    text: str
    date: str
    confidence: float = Field(ge=0.0, le=1.0)
    url: str


class TimingMs(BaseModel):
    roast_ready: int
    total: int


class EngineResponse(BaseModel):
    """Output contract — consumed by Person 1 (overlay) and Person 4 (dashboard)."""

    roast: str
    overall_score: int
    primary_category: str
    category_scores: dict[str, int]
    diagnosis: str
    lesson: str
    improved_prompt: str
    severity: int
    should_interrupt: bool
    personality_id: str
    voice_id: str
    audio_url: str
    audio_cache_key: str
    audio_status: AudioStatus
    action: str
    timing_ms: TimingMs
    source: SourceCitation | None = None  # set when a knowledge record informed the verdict
