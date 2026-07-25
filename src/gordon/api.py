"""FastAPI routes."""

from __future__ import annotations

import string

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from gordon import classifier, config, engine, voice
from gordon.schemas import CaptureEvent, ClassifierVerdict, EngineResponse

app = FastAPI(title="Gordon Engine", version="0.1.0")

_MEDIA_TYPES = {".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".aiff": "audio/aiff"}
_HEX = set(string.hexdigits)


@app.get("/health")
async def health() -> dict[str, object]:
    return {"status": "ok", "config": config.health_status()}


@app.post("/classify")
async def classify(event: CaptureEvent) -> ClassifierVerdict:
    """Pre-gate: same CaptureEvent JSON as /evaluate; verdict on whether the
    event deserves the full roast pipeline."""
    return await classifier.classify(event)


@app.post("/evaluate")
async def evaluate(event: CaptureEvent) -> EngineResponse:
    try:
        return await engine.evaluate(event)
    except RuntimeError as exc:
        print(f"[api] evaluate failed: {exc}")
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/audio/{key}")
async def audio(key: str) -> FileResponse:
    if not key or set(key) - _HEX:
        raise HTTPException(status_code=400, detail="bad audio key")
    # Synthesis may still be streaming when the overlay asks — wait briefly.
    path = await voice.wait_for_audio(key)
    if path is None:
        raise HTTPException(status_code=404, detail="audio not ready or synthesis failed")
    return FileResponse(path, media_type=_MEDIA_TYPES.get(path.suffix, "application/octet-stream"))
