"""API routes via ASGI transport with the engine monkeypatched — zero network."""

from __future__ import annotations

import httpx
import pytest

from gordon import api, config, engine
from gordon.schemas import EngineResponse, TimingMs

SCORES = {
    "prompt_specificity": 15, "token_conservation": 80, "frontier_awareness": 70,
    "tool_selection": 60, "context_management": 25, "verification": 20,
}

CANNED = EngineResponse(
    roast="Send it back.", overall_score=31, primary_category="prompt_specificity",
    category_scores=SCORES, diagnosis="d", lesson="l", improved_prompt="i",
    severity=2, should_interrupt=True, personality_id="angry_chef", voice_id="v",
    audio_url="/audio/abc123", audio_cache_key="abc123", audio_status="streaming",
    action="desk_buzzer", timing_ms=TimingMs(roast_ready=900, total=2100),
)


@pytest.fixture
def client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=api.app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_health_reports_config(client) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "anthropic_key" in body["config"] and "elevenlabs_key" in body["config"]


async def test_evaluate_happy_path(client, monkeypatch) -> None:
    async def fake_evaluate(event, **kwargs):
        return CANNED

    monkeypatch.setattr(engine, "evaluate", fake_evaluate)
    response = await client.post("/evaluate", json={"event_id": "e1", "prompt_text": "Make this work"})
    assert response.status_code == 200
    assert response.json()["roast"] == "Send it back."


async def test_evaluate_malformed_input_422(client) -> None:
    response = await client.post("/evaluate", json={"event_id": "e1"})  # no prompt_text
    assert response.status_code == 422


async def test_evaluate_engine_failure_502(client, monkeypatch) -> None:
    async def broken(event, **kwargs):
        raise RuntimeError("evaluation failed after 2 attempts")

    monkeypatch.setattr(engine, "evaluate", broken)
    response = await client.post("/evaluate", json={"event_id": "e1", "prompt_text": "x"})
    assert response.status_code == 502


async def test_audio_bad_key_400(client) -> None:
    response = await client.get("/audio/../../etc/passwd")
    assert response.status_code in (400, 404)  # path either sanitized by router or rejected by us
    response = await client.get("/audio/nothex!!")
    assert response.status_code == 400


async def test_audio_unknown_key_404_fast(client, monkeypatch) -> None:
    monkeypatch.setattr(config, "AUDIO_READY_TIMEOUT_S", 0.2)
    monkeypatch.setattr(config, "AUDIO_READY_POLL_S", 0.05)
    response = await client.get("/audio/" + "a" * 24)
    assert response.status_code == 404


async def test_audio_serves_file_with_media_type(client, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "AUDIO_CACHE_DIR", tmp_path)
    key = "b" * 24
    (tmp_path / f"{key}.mp3").write_bytes(b"ID3fake")
    response = await client.get(f"/audio/{key}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
