"""Voice layer: cache keys, .part discipline, 422 speed retry, fallbacks.
httpx is mocked with MockTransport — zero network."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from gordon import config, voice


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "AUDIO_CACHE_DIR", tmp_path)
    monkeypatch.setattr(voice, "_client", None)
    monkeypatch.setattr(voice, "_semaphore", None)
    voice._in_flight.clear()
    yield


def _install_transport(monkeypatch, handler) -> None:
    client = httpx.AsyncClient(
        base_url=config.ELEVENLABS_BASE_URL, transport=httpx.MockTransport(handler)
    )
    monkeypatch.setattr(voice, "_get_client", lambda: client)


SETTINGS = {"stability": 0.4, "similarity_boost": 0.75, "style": 0.6}


def test_cache_key_sensitive_to_every_component() -> None:
    base = voice.cache_key("text", "voice", SETTINGS, "model")
    assert voice.cache_key("text2", "voice", SETTINGS, "model") != base
    assert voice.cache_key("text", "voice2", SETTINGS, "model") != base
    assert voice.cache_key("text", "voice", {**SETTINGS, "style": 0.61}, "model") != base
    assert voice.cache_key("text", "voice", SETTINGS, "model2") != base
    assert voice.cache_key("text", "voice", SETTINGS, "model") == base  # stable


async def test_happy_path_writes_mp3_via_part(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"ID3fake-mp3-bytes")

    _install_transport(monkeypatch, handler)
    dest = config.AUDIO_CACHE_DIR / "k1.mp3"
    await voice._elevenlabs_stream("hello", "voice-id", SETTINGS, dest)
    assert dest.read_bytes() == b"ID3fake-mp3-bytes"
    assert not list(config.AUDIO_CACHE_DIR.glob("*.part"))


async def test_failure_leaves_no_truncated_file(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b"boom")

    _install_transport(monkeypatch, handler)
    dest = config.AUDIO_CACHE_DIR / "k2.mp3"
    with pytest.raises(httpx.HTTPStatusError):
        await voice._elevenlabs_stream("hello", "voice-id", SETTINGS, dest)
    assert not dest.exists()
    assert not list(config.AUDIO_CACHE_DIR.glob("*.part"))


async def test_422_retries_without_speed(monkeypatch) -> None:
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(request.content)
        bodies.append(body)
        if "speed" in body["voice_settings"]:
            return httpx.Response(422, content=b'{"detail":"speed not allowed"}')
        return httpx.Response(200, content=b"mp3")

    _install_transport(monkeypatch, handler)
    path = await voice._synthesize("hi", "voice-id", {**SETTINGS, "speed": 1.1}, "k3")
    assert path is not None and path.suffix == ".mp3" and path.exists()
    assert len(bodies) == 2
    assert "speed" in bodies[0]["voice_settings"] and "speed" not in bodies[1]["voice_settings"]


async def test_cache_hit_short_circuits(monkeypatch) -> None:
    key = voice.cache_key("hello", "voice-id", SETTINGS, config.ELEVENLABS_MODEL_ID)
    (config.AUDIO_CACHE_DIR / f"{key}.mp3").write_bytes(b"cached")
    monkeypatch.setattr(config, "ELEVENLABS_API_KEY", "set")
    handle = voice.start_synthesis("hello", "voice-id", SETTINGS)
    assert handle.status == "cached" and handle.task is None


async def test_no_key_no_darwin_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(config, "ELEVENLABS_API_KEY", "")
    monkeypatch.setattr(voice.sys, "platform", "linux")
    handle = voice.start_synthesis("hello", "voice-id", SETTINGS)
    assert handle.status == "unavailable" and handle.task is None


async def test_same_key_in_flight_dedups(monkeypatch) -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow(request: httpx.Request):
        started.set()
        await release.wait()
        return httpx.Response(200, content=b"mp3")

    _install_transport(monkeypatch, lambda req: httpx.Response(200, content=b"mp3"))
    monkeypatch.setattr(config, "ELEVENLABS_API_KEY", "set")

    async def never_finishes(*a, **k):
        started.set()
        await release.wait()

    monkeypatch.setattr(voice, "_synthesize", never_finishes)
    h1 = voice.start_synthesis("hello", "voice-id", SETTINGS)
    await started.wait()
    h2 = voice.start_synthesis("hello", "voice-id", SETTINGS)
    assert h1.key == h2.key
    assert h2.task is h1.task  # second caller reuses the in-flight task, no double writer
    release.set()
    await h1.task


async def test_wait_for_audio_times_out_fast(monkeypatch) -> None:
    monkeypatch.setattr(config, "AUDIO_READY_TIMEOUT_S", 0.3)
    monkeypatch.setattr(config, "AUDIO_READY_POLL_S", 0.05)
    assert await voice.wait_for_audio("deadbeef" * 3) is None
