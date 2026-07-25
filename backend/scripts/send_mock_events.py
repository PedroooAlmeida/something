#!/usr/bin/env python3
"""Send the PRD demo-scenario events to the platform service.

Usage:  python scripts/send_mock_events.py [--base http://127.0.0.1:8765]

Lets Person 4 exercise the full pipeline (and Person 1 develop the overlay
against real WebSocket pushes) before capture and the AI engine exist.
"""
import argparse
import json
import urllib.request
import uuid
from datetime import datetime, timezone

SCENARIOS = [
    ("Scene 1 — Bad prompt", "Build me an app.", "unknown"),
    ("Scene 2 — Token waste",
     ("Our company was founded in 2019 by two friends who met at a coffee shop. "
      "We value synergy, hustle, and radical candor. " * 60) +
     "\nMeeting transcript #1: ...\nMeeting transcript #2: ...\nMeeting transcript #3: ...\n"
     "Anyway the login button is broken, fix it.",
     "unknown"),
    ("Scene 3 — Outdated technology",
     "Write me a date picker component using moment.js and create-react-app, "
     "targeting react 18.",
     "claude-3-opus"),
    ("Scene 4 — A good prompt (control)",
     "In auth.ts, login() returns a 401 after the access token expires. Expected: "
     "the client should refresh the token and retry once. I already tried bumping "
     "the expiry. Find the cause, fix the refresh logic without changing the public "
     "API, and write a test that reproduces the bug.",
     "claude-fable-5"),
]


def post(base: str, path: str, payload: dict) -> dict:
    req = urllib.request.Request(base + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8765")
    args = ap.parse_args()

    session = f"mock-session-{uuid.uuid4().hex[:6]}"
    for name, prompt, model in SCENARIOS:
        event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "mock_script",
            "application": "supported_ai_tool",
            "prompt_text": prompt,
            "selected_model": model,
            "session_id": session,
        }
        result = post(args.base, "/api/events", event)
        ev = result.get("evaluation") or {}
        print(f"\n=== {name} ===")
        print(f"prompt: {prompt[:80]!r}{'...' if len(prompt) > 80 else ''}")
        print(f"score: {ev.get('overall_score')}  primary: {ev.get('primary_category')}  "
              f"severity: {ev.get('severity')}  action: {ev.get('action')}")
        print(f"roast: {ev.get('roast')}")

    print("\nDashboard summary:")
    with urllib.request.urlopen(args.base + "/api/dashboard/summary", timeout=15) as resp:
        print(json.dumps(json.loads(resp.read().decode()), indent=2))


if __name__ == "__main__":
    main()
