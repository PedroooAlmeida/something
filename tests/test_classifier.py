"""Roastworthiness classifier: heuristic fast paths never call the model;
LLM path parses and degrades safely. Zero network."""

from __future__ import annotations

import json

import pytest

from gordon import classifier
from gordon.schemas import CaptureEvent


def _event(text: str) -> CaptureEvent:
    return CaptureEvent(event_id="c1", prompt_text=text)


@pytest.fixture(autouse=True)
def llm_must_not_be_called_unless_expected(monkeypatch):
    """Default: any stream_llm call explodes. Tests that expect an LLM call
    override with their own mock."""

    async def forbidden(prompt, **kwargs):
        raise AssertionError("stream_llm called on a heuristic path")
        yield  # pragma: no cover

    monkeypatch.setattr(classifier.llm, "stream_llm", forbidden)


async def test_empty_capture_short_circuits() -> None:
    verdict = await classifier.classify(_event("   "))
    assert verdict.roastworthy is False
    assert verdict.confidence == 1.0


async def test_single_char_short_circuits() -> None:
    verdict = await classifier.classify(_event("j"))
    assert verdict.roastworthy is False


@pytest.mark.parametrize(
    "secret",
    [
        "here is my key sk-abc123def456ghi789jkl012",
        "password: hunter2io",
        "ghp_abcdefghijklmnopqrstuv123456",
        "-----BEGIN RSA PRIVATE KEY-----",
        "AKIAIOSFODNN7EXAMPLE is my aws key",
    ],
)
async def test_secret_looking_capture_never_roasted(secret: str) -> None:
    verdict = await classifier.classify(_event(secret))
    assert verdict.roastworthy is False
    assert "credential" in verdict.reason or "secret" in verdict.reason.lower()


async def test_llm_verdict_parsed(monkeypatch) -> None:
    payload = {
        "roastworthy": True,
        "confidence": 0.92,
        "reason": "Three vague words, no goal.",
        "category_hint": "prompt_specificity",
    }

    async def mock_stream(prompt, **kwargs):
        yield json.dumps(payload)

    monkeypatch.setattr(classifier.llm, "stream_llm", mock_stream)
    verdict = await classifier.classify(_event("Make this work"))
    assert verdict.roastworthy is True
    assert verdict.category_hint == "prompt_specificity"


async def test_unknown_category_hint_normalized_to_none(monkeypatch) -> None:
    async def mock_stream(prompt, **kwargs):
        yield json.dumps(
            {"roastworthy": True, "confidence": 0.5, "reason": "r", "category_hint": "vibes"}
        )

    monkeypatch.setattr(classifier.llm, "stream_llm", mock_stream)
    verdict = await classifier.classify(_event("Make this work"))
    assert verdict.category_hint is None


async def test_unparseable_verdict_defaults_to_roastworthy(monkeypatch) -> None:
    async def mock_stream(prompt, **kwargs):
        yield "the model rambled instead of emitting JSON"

    monkeypatch.setattr(classifier.llm, "stream_llm", mock_stream)
    verdict = await classifier.classify(_event("Make this work"))
    assert verdict.roastworthy is True  # never block the pipeline on classifier failure
    assert verdict.confidence <= 0.5
