"""Wire contracts: Person 2's sample input parses verbatim; response carries
every contract key; six category scores always enforced."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from gordon.schemas import CaptureEvent, EngineResponse, Evaluation, TimingMs

PERSON_2_SAMPLE = {
    "event_id": "uuid",
    "timestamp": "2026-07-24T12:00:00Z",
    "source": "chat_application",
    "application": "cursor",
    "prompt_text": "Make this work",
    "selected_model": "unknown",
    "screenshot_path": "/tmp/x.png",
    "session_id": "abc",
    "personality_id": "angry_chef",
}

SCORES = {
    "prompt_specificity": 15, "token_conservation": 80, "frontier_awareness": 70,
    "tool_selection": 60, "context_management": 25, "verification": 20,
}


def test_person2_contract_parses_verbatim() -> None:
    event = CaptureEvent.model_validate(PERSON_2_SAMPLE)
    assert event.prompt_text == "Make this work"
    assert event.personality_id == "angry_chef"


def test_minimal_event_still_valid() -> None:
    event = CaptureEvent(event_id="e", prompt_text="hi")
    assert event.personality_id == "angry_chef"
    assert event.screenshot_path is None


def test_missing_category_rejected() -> None:
    bad = dict(SCORES)
    del bad["verification"]
    with pytest.raises(ValidationError):
        Evaluation(
            roast="x", overall_score=10, primary_category="prompt_specificity",
            category_scores=bad, diagnosis="d", lesson="l", improved_prompt="i",
            severity=2, should_interrupt=True,
        )


def test_scores_clamped_to_0_100() -> None:
    evaluation = Evaluation(
        roast="x", overall_score=10, primary_category="prompt_specificity",
        category_scores={**SCORES, "verification": 400}, diagnosis="d", lesson="l",
        improved_prompt="i", severity=2, should_interrupt=True,
    )
    assert evaluation.category_scores["verification"] == 100


def test_unknown_primary_category_rejected() -> None:
    with pytest.raises(ValidationError):
        Evaluation(
            roast="x", overall_score=10, primary_category="vibes",
            category_scores=SCORES, diagnosis="d", lesson="l", improved_prompt="i",
            severity=2, should_interrupt=True,
        )


def test_response_serializes_all_contract_keys() -> None:
    response = EngineResponse(
        roast="r", overall_score=31, primary_category="prompt_specificity",
        category_scores=SCORES, diagnosis="d", lesson="l", improved_prompt="i",
        severity=2, should_interrupt=True, personality_id="angry_chef",
        voice_id="v", audio_url="/audio/k", audio_cache_key="k",
        audio_status="streaming", action="desk_buzzer",
        timing_ms=TimingMs(roast_ready=900, total=2100),
    )
    payload = response.model_dump()
    assert set(payload) == {
        "roast", "overall_score", "primary_category", "category_scores", "diagnosis",
        "lesson", "improved_prompt", "severity", "should_interrupt", "personality_id",
        "voice_id", "audio_url", "audio_cache_key", "audio_status", "action", "timing_ms",
    }
    assert payload["timing_ms"] == {"roast_ready": 900, "total": 2100}


def test_bad_audio_status_rejected() -> None:
    with pytest.raises(ValidationError):
        EngineResponse(
            roast="r", overall_score=31, primary_category="prompt_specificity",
            category_scores=SCORES, diagnosis="d", lesson="l", improved_prompt="i",
            severity=2, should_interrupt=True, personality_id="angry_chef",
            voice_id="v", audio_url="/audio/k", audio_cache_key="k",
            audio_status="buffering", action="none",
            timing_ms=TimingMs(roast_ready=1, total=2),
        )
