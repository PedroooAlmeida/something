#!/usr/bin/env python3
"""Bridge: Person 2's capture service -> Person 4's platform API.

Their watcher writes roast events as JSON files into roast_events/ (their
emitter.py). This bridge tails that folder, maps each file to the shared
PRD section 17 CaptureEvent, and POSTs it to /api/events. Processed files
move to roast_events/processed/ so nothing fires twice.

Usage:
  python scripts/capture_bridge.py --events-dir ../roast_events \
         [--base https://gordon-platform.fly.dev] [--session demo-1]
"""
import argparse
import json
import os
import shutil
import time
import urllib.request
import uuid
from datetime import datetime, timezone

POLL_S = 0.5


def map_event(raw: dict, session_id: str) -> dict:
    """Person 2's shape {kind, ts, app, text, score, category, severity, evidence}
    -> shared CaptureEvent. Their local score/category/severity are hints only —
    the pipeline's evaluator is the source of truth."""
    ts = raw.get("iso")
    if not ts and raw.get("ts"):
        ts = datetime.fromtimestamp(float(raw["ts"]), timezone.utc).isoformat()
    return {
        "event_id": raw.get("event_id") or str(uuid.uuid4()),
        "timestamp": ts or datetime.now(timezone.utc).isoformat(),
        "source": f"screen_capture:{raw.get('kind', 'unknown')}",
        "application": raw.get("app") or "unknown",
        "prompt_text": raw.get("text") or raw.get("evidence") or "",
        "selected_model": raw.get("model") or "unknown",
        "session_id": session_id,
    }


def post(base: str, event: dict) -> dict:
    req = urllib.request.Request(base + "/api/events",
                                 data=json.dumps(event).encode(),
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--events-dir", default="roast_events")
    ap.add_argument("--base", default="http://127.0.0.1:8765")
    ap.add_argument("--session", default=f"capture-{uuid.uuid4().hex[:6]}")
    args = ap.parse_args()

    processed_dir = os.path.join(args.events_dir, "processed")
    os.makedirs(processed_dir, exist_ok=True)
    print(f"[bridge] watching {args.events_dir} -> {args.base} (session {args.session})")

    while True:
        try:
            names = sorted(n for n in os.listdir(args.events_dir) if n.endswith(".json"))
        except FileNotFoundError:
            time.sleep(POLL_S)
            continue
        for name in names:
            path = os.path.join(args.events_dir, name)
            try:
                with open(path) as f:
                    raw = json.load(f)
                event = map_event(raw, args.session)
                if not event["prompt_text"]:
                    print(f"[bridge] skip {name}: empty text")
                else:
                    result = post(args.base, event)
                    ev = result.get("evaluation") or {}
                    print(f"[bridge] {name} -> score {ev.get('overall_score')} "
                          f"{ev.get('primary_category')} sev {ev.get('severity')}"
                          if result.get("evaluated") else f"[bridge] {name} -> {result.get('status')}")
            except Exception as exc:
                print(f"[bridge] error on {name}: {exc}")
            shutil.move(path, os.path.join(processed_dir, name))
        time.sleep(POLL_S)


if __name__ == "__main__":
    main()
