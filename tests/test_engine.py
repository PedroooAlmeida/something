"""Engine pipeline with mocked stream_llm and voice — zero network.

Verifies the demo invariants: synthesis fires BEFORE the stream ends (1),
synth failure never blocks the JSON (2), safety runs before synthesis (3),
all six category keys present, timing fields populated.
"""

from __future__ import annotations

import json

import pytest

from gordon import engine, voice
from gordon.schemas import CaptureEvent

GOOD_PAYLOAD = {
    "roast": 'You typed "Make this work" and called it engineering. Send it back.',
    "overall_score": 22,
    "primary_category": "prompt_specificity",
    "category_scores": {
        "prompt_specificity": 10,
        "token_conservation": 70,
        "frontier_awareness": 70,
        "tool_selection": 55,
        "context_management": 25,
        "verification": 20,
    },
    "diagnosis": "No goal, no context, no definition of done.",
    "lesson": "State the goal and what done looks like.",
    "improved_prompt": "Fix the TypeError in checkout.py line 40; test with pytest tests/test_checkout.py.",
    "severity": 3,
    "should_interrupt": True,
}


def _event(prompt: str = "Make this work") -> CaptureEvent:
    return CaptureEvent(event_id="evt-1", prompt_text=prompt, personality_id="angry_chef")


def _mock_stream(payload: dict, chunk_size: int = 7):
    """Chunk the serialized payload at hostile boundaries."""
    text = json.dumps(payload)

    async def stream(prompt, **kwargs):
        for i in range(0, len(text), chunk_size):
            yield text[i : i + chunk_size]

    return stream


@pytest.fixture
def synth_calls(monkeypatch):
    """Replace voice.start_synthesis with a recorder; track call order vs stream end."""
    calls: list[dict] = []

    def fake_start(text: str, voice_id: str, settings: dict) -> voice.SynthHandle:
        calls.append({"text": text, "voice_id": voice_id, "settings": settings})
        return voice.SynthHandle("a" * 24, "streaming", None)

    monkeypatch.setattr(voice, "start_synthesis", fake_start)
    return calls


async def test_full_pipeline_contract(monkeypatch, synth_calls) -> None:
    monkeypatch.setattr(engine.llm, "stream_llm", _mock_stream(GOOD_PAYLOAD))
    response = await engine.evaluate(_event())
    assert set(response.category_scores) == {
        "prompt_specificity", "token_conservation", "frontier_awareness",
        "tool_selection", "context_management", "verification",
    }
    assert response.overall_score == 22
    assert response.should_interrupt is True
    assert response.action == "bell_bot"  # severity 3 per platform action enum
    assert response.source is None  # no knowledge record matched "Make this work"
    assert response.audio_status == "streaming"
    assert response.audio_url == f"/audio/{response.audio_cache_key}"
    assert response.timing_ms.total >= response.timing_ms.roast_ready >= 0


async def test_synthesis_fires_before_stream_end(monkeypatch, synth_calls) -> None:
    """Invariant 1: audio starts at the roast's closing quote, mid-stream."""
    text = json.dumps(GOOD_PAYLOAD)
    seen_after_synth: list[str] = []

    async def stream(prompt, **kwargs):
        for i in range(0, len(text), 5):
            if synth_calls:
                seen_after_synth.append(text[i : i + 5])
            yield text[i : i + 5]

    monkeypatch.setattr(engine.llm, "stream_llm", stream)
    await engine.evaluate(_event())
    assert synth_calls, "synthesis never fired"
    assert seen_after_synth, "synthesis only fired after the stream was fully consumed"


async def test_safety_runs_before_synthesis(monkeypatch, synth_calls) -> None:
    """Invariant 3: the fabricated sentence never reaches the synthesizer."""
    payload = dict(GOOD_PAYLOAD, roast="This is 40% slower than GPT-9. Bland, vague, hopeless.")
    monkeypatch.setattr(engine.llm, "stream_llm", _mock_stream(payload))
    response = await engine.evaluate(_event())
    assert synth_calls[0]["text"] == "Bland, vague, hopeless."
    assert response.roast == "Bland, vague, hopeless."


async def test_synth_failure_never_blocks_response(monkeypatch) -> None:
    """Invariant 2: voice layer says unavailable, JSON still returns."""
    monkeypatch.setattr(engine.llm, "stream_llm", _mock_stream(GOOD_PAYLOAD))
    monkeypatch.setattr(
        voice, "start_synthesis", lambda *a, **k: voice.SynthHandle("b" * 24, "unavailable", None)
    )
    response = await engine.evaluate(_event())
    assert response.audio_status == "unavailable"
    assert response.roast


async def test_retry_on_garbage_then_success(monkeypatch, synth_calls) -> None:
    attempts = {"n": 0}
    good = json.dumps(GOOD_PAYLOAD)

    async def flaky(prompt, **kwargs):
        attempts["n"] += 1
        if attempts["n"] == 1:
            yield "sorry, I cannot produce JSON today"
        else:
            yield good

    monkeypatch.setattr(engine.llm, "stream_llm", flaky)
    response = await engine.evaluate(_event())
    assert attempts["n"] == 2
    assert response.overall_score == 22


async def test_two_attempts_then_error(monkeypatch, synth_calls) -> None:
    async def broken(prompt, **kwargs):
        yield "not json"

    monkeypatch.setattr(engine.llm, "stream_llm", broken)
    with pytest.raises(RuntimeError):
        await engine.evaluate(_event())


async def test_no_interrupt_means_no_action(monkeypatch, synth_calls) -> None:
    payload = dict(GOOD_PAYLOAD, overall_score=90, severity=1, should_interrupt=False)
    monkeypatch.setattr(engine.llm, "stream_llm", _mock_stream(payload))
    response = await engine.evaluate(_event("A genuinely precise prompt"))
    assert response.action == "none"


async def test_source_citation_populated_on_knowledge_match(monkeypatch, synth_calls) -> None:
    monkeypatch.setattr(engine.llm, "stream_llm", _mock_stream(GOOD_PAYLOAD))
    response = await engine.evaluate(
        _event("Write a React class component using componentWillMount"), with_audio=False
    )
    assert response.source is not None
    assert response.source.url.startswith("https://")
    assert response.source.date == "2024-12-05"
    assert 0.0 <= response.source.confidence <= 1.0


async def test_identical_input_same_scores_different_personality(monkeypatch, synth_calls) -> None:
    """M4 shape check (text half): same evaluation, personality only changes voice/roast style."""
    monkeypatch.setattr(engine.llm, "stream_llm", _mock_stream(GOOD_PAYLOAD))
    chef = await engine.evaluate(_event())
    prof_event = CaptureEvent(
        event_id="evt-2", prompt_text="Make this work", personality_id="disappointed_professor"
    )
    prof = await engine.evaluate(prof_event)
    assert chef.category_scores == prof.category_scores
    assert chef.personality_id == "angry_chef"
    assert prof.personality_id == "disappointed_professor"
