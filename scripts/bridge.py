"""LOCAL DEBUG ONLY: capture events -> engine directly, skipping the platform.

The canonical demo path is backend/scripts/capture_bridge.py (capture ->
/api/events); the backend calls this engine's /evaluate itself (set
GORDON_ENGINE_URL) so the overlay WS, dashboard, webhooks, and buzzer all
fire. Use this script only to exercise the engine without the backend.

Run the engine first:   uvicorn gordon.api:app --port 8001
Then:                    python scripts/bridge.py [--events-dir roast_events] [--engine http://127.0.0.1:8001]
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import httpx


def to_capture_event(raw: dict, personality_id: str) -> dict:
    """Map the capture component's event shape onto the engine's CaptureEvent contract."""
    behavior = raw.get("behavior") or {}
    prompt_text = behavior.get("text") or raw.get("evidence") or ""
    return {
        "event_id": raw.get("event_id", ""),
        "timestamp": raw.get("iso", ""),
        "source": "screen_capture",
        "application": raw.get("app", ""),
        "prompt_text": prompt_text,
        "selected_model": raw.get("selected_model") or "unknown",
        "screenshot_path": None,
        "session_id": raw.get("window_title", ""),
        "personality_id": personality_id,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="capture -> engine bridge")
    parser.add_argument("--events-dir", default="roast_events")
    parser.add_argument("--engine", default="http://127.0.0.1:8001")
    parser.add_argument("--personality", default="angry_chef")
    parser.add_argument("--poll-s", type=float, default=0.5)
    args = parser.parse_args()

    events_dir = Path(args.events_dir)
    events_dir.mkdir(exist_ok=True)
    seen: set[Path] = set(events_dir.glob("*.json"))
    print(f"[bridge] watching {events_dir}/ -> {args.engine}/evaluate ({len(seen)} old events ignored)")

    with httpx.Client(base_url=args.engine, timeout=60.0) as client:
        while True:
            for path in sorted(events_dir.glob("*.json")):
                if path in seen:
                    continue
                seen.add(path)
                try:
                    raw = json.loads(path.read_text())
                    event = to_capture_event(raw, args.personality)
                    if not event["prompt_text"]:
                        print(f"[bridge] {path.name}: no text/evidence, skipped")
                        continue
                    response = client.post("/evaluate", json=event)
                    response.raise_for_status()
                    body = response.json()
                    print(
                        f"[bridge] {path.name}: score={body['overall_score']} "
                        f"{body['primary_category']} audio={args.engine}{body['audio_url']}\n"
                        f"         roast: {body['roast']}"
                    )
                except (OSError, json.JSONDecodeError, httpx.HTTPError) as exc:
                    print(f"[bridge] {path.name} failed: {exc}")
            time.sleep(args.poll_s)


if __name__ == "__main__":
    main()
