"""ElevenLabs synthesis, on-disk cache, fallback chain, prewarm.

Fallback chain: cache hit -> ElevenLabs stream -> macOS `say` system TTS -> unavailable.
Audio never blocks the engine response: synthesis runs as a background task and
/audio/{key} waits for the file to land.

Verified against current ElevenLabs docs (2026-07):
POST /v1/text-to-speech/{voice_id}/stream, header xi-api-key, body
{text, model_id, voice_settings}; low-latency tier model is eleven_flash_v2_5.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import httpx

from gordon import config
from gordon.schemas import AudioStatus

_SUFFIXES = (".mp3", ".m4a", ".aiff")
_client: httpx.AsyncClient | None = None
_semaphore: asyncio.Semaphore | None = None  # free tier allows 2 concurrent streams
_in_flight: dict[str, asyncio.Task] = {}  # same-key dedup: never two writers on one .part


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=config.ELEVENLABS_BASE_URL,
            timeout=config.ELEVENLABS_TIMEOUT_S,
        )
    return _client


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(config.ELEVENLABS_MAX_CONCURRENCY)
    return _semaphore


def cache_key(text: str, voice_id: str, settings: dict, model_id: str) -> str:
    """Hash of everything that affects the waveform — changing any voice setting
    must produce a new key (stale-audio gotcha)."""
    payload = json.dumps(
        {"text": text, "voice_id": voice_id, "settings": settings, "model_id": model_id},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[: config.AUDIO_KEY_LENGTH]


def find_audio(key: str) -> Path | None:
    for suffix in _SUFFIXES:
        p = config.AUDIO_CACHE_DIR / f"{key}{suffix}"
        if p.exists():
            return p
    return None


@dataclass
class SynthHandle:
    key: str
    status: AudioStatus
    task: asyncio.Task | None = None


def start_synthesis(text: str, voice_id: str, settings: dict) -> SynthHandle:
    """Decide the audio path and kick it off WITHOUT awaiting it (invariant 2).

    Status reflects the state at response time:
    cached (file already on disk) | streaming (ElevenLabs task launched) |
    fallback_system_tts (no key/voice, system TTS launched) | unavailable.
    """
    config.AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = cache_key(text, voice_id, settings, config.ELEVENLABS_MODEL_ID)
    if find_audio(key):
        return SynthHandle(key, "cached")
    if existing := _in_flight.get(key):
        if not existing.done():
            return SynthHandle(key, "streaming", existing)
    if config.ELEVENLABS_API_KEY and voice_id:
        return SynthHandle(key, "streaming", _spawn(key, _synthesize(text, voice_id, settings, key)))
    if sys.platform == "darwin":
        return SynthHandle(key, "fallback_system_tts", _spawn(key, _system_tts(text, key)))
    return SynthHandle(key, "unavailable")


def _spawn(key: str, coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _in_flight[key] = task
    task.add_done_callback(lambda t: _finish(key, t))
    return task


def _finish(key: str, task: asyncio.Task) -> None:
    # only evict our own entry — a stale callback must not evict a newer task
    # for the same key (that would allow two concurrent writers on one .part)
    if _in_flight.get(key) is task:
        _in_flight.pop(key, None)
    if not task.cancelled() and (exc := task.exception()):
        print(f"[voice] synth task for {key} died: {exc}")


async def _synthesize(text: str, voice_id: str, settings: dict, key: str) -> Path | None:
    """ElevenLabs streaming synth; falls back to system TTS on any failure."""
    dest = config.AUDIO_CACHE_DIR / f"{key}.mp3"
    try:
        await _elevenlabs_stream(text, voice_id, settings, dest)
        return dest
    except httpx.HTTPStatusError as exc:
        body = exc.response.text[:300]
        print(f"[voice] ElevenLabs {exc.response.status_code}: {body}")
        # account-tier gotcha: `speed` may be rejected — drop it and retry once
        if exc.response.status_code == 422 and "speed" in settings:
            retry = {k: v for k, v in settings.items() if k != "speed"}
            try:
                await _elevenlabs_stream(text, voice_id, retry, dest)
                return dest
            except Exception as exc2:  # noqa: BLE001 — degrade, never crash the task
                print(f"[voice] retry without speed failed: {exc2}")
    except Exception as exc:  # noqa: BLE001 — degrade, never crash the task
        print(f"[voice] ElevenLabs synth failed: {exc}")
    if sys.platform == "darwin":
        return await _system_tts(text, key)
    return None


async def _elevenlabs_stream(text: str, voice_id: str, settings: dict, dest: Path) -> None:
    """POST /v1/text-to-speech/{voice_id}/stream, chunks to .part, rename on success
    so a failed request never leaves a truncated mp3 in the cache."""
    part = dest.with_suffix(".mp3.part")
    async with _get_semaphore():
        try:
            async with _get_client().stream(
                "POST",
                f"/v1/text-to-speech/{voice_id}/stream",
                params={"output_format": config.ELEVENLABS_OUTPUT_FORMAT},
                headers={"xi-api-key": config.ELEVENLABS_API_KEY, "accept": "audio/mpeg"},
                json={
                    "text": text,
                    "model_id": config.ELEVENLABS_MODEL_ID,
                    "voice_settings": settings,
                },
            ) as response:
                if response.status_code >= 400:
                    await response.aread()
                    response.raise_for_status()
                with part.open("wb") as fh:
                    async for chunk in response.aiter_bytes():
                        fh.write(chunk)
            part.rename(dest)
        finally:
            part.unlink(missing_ok=True)


async def _system_tts(text: str, key: str) -> Path | None:
    """macOS `say` fallback straight to AAC/.m4a (plays in every browser);
    aiff + afconvert as the second try on older macOS. All writes stage through
    non-servable names so /audio pollers never see a partial file."""
    if text.startswith("-"):
        text = " " + text  # argv injection guard: never let text parse as a `say` flag
    m4a = config.AUDIO_CACHE_DIR / f"{key}.m4a"
    part = config.AUDIO_CACHE_DIR / f"{key}.m4a.part"
    # ".part.aiff" keeps say's extension sniffing happy and is invisible to find_audio()
    aiff_tmp = config.AUDIO_CACHE_DIR / f"{key}.part.aiff"
    try:
        proc = await asyncio.create_subprocess_exec(
            "say", "-o", str(part), "--file-format=m4af", "--data-format=aac", text,
            stderr=asyncio.subprocess.DEVNULL,
        )
        if await proc.wait() == 0 and part.exists():
            part.rename(m4a)
            return m4a
        part.unlink(missing_ok=True)

        proc = await asyncio.create_subprocess_exec("say", "-o", str(aiff_tmp), text)
        if await proc.wait() != 0 or not aiff_tmp.exists():
            print("[voice] system `say` failed")
            return None
        conv = await asyncio.create_subprocess_exec(
            "afconvert", "-f", "m4af", "-d", "aac", str(aiff_tmp), str(m4a),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        if await conv.wait() == 0 and m4a.exists():
            aiff_tmp.unlink(missing_ok=True)
            return m4a
        final_aiff = config.AUDIO_CACHE_DIR / f"{key}.aiff"
        aiff_tmp.rename(final_aiff)
        return final_aiff
    except OSError as exc:
        print(f"[voice] system TTS failed: {exc}")
        part.unlink(missing_ok=True)
        aiff_tmp.unlink(missing_ok=True)
        return None


async def wait_for_audio(key: str, timeout_s: float | None = None) -> Path | None:
    """Poll the cache until the audio file lands (used by GET /audio/{key})."""
    deadline = asyncio.get_event_loop().time() + (timeout_s or config.AUDIO_READY_TIMEOUT_S)
    while True:
        path = find_audio(key)
        if path:
            return path
        if asyncio.get_event_loop().time() >= deadline:
            return None
        await asyncio.sleep(config.AUDIO_READY_POLL_S)


async def prewarm(items: list[tuple[str, str, dict]]) -> list[str]:
    """Synthesize (text, voice_id, settings) tuples ahead of the demo; returns keys."""
    keys: list[str] = []
    for text, voice_id, settings in items:
        handle = start_synthesis(text, voice_id, settings)
        keys.append(handle.key)
        if handle.task:
            await handle.task
    return keys
