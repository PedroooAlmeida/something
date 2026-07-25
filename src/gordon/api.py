"""FastAPI routes."""

from __future__ import annotations

from fastapi import FastAPI

from gordon import config

app = FastAPI(title="Gordon Engine", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, object]:
    return {"status": "ok", "config": config.health_status()}
