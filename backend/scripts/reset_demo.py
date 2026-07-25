#!/usr/bin/env python3
"""One-command demo reset (PRD final hour: 'resetting the demo state').

- wipes events/evaluations/screenshots
- resumes monitoring
- resets personality to angry_chef
- ensures the buzzer webhook is registered exactly once
- optionally fires one test violation so devices/overlay prove they're alive

Usage: python scripts/reset_demo.py [--base https://gordon-platform.fly.dev]
       [--buzzer-url http://127.0.0.1:9999/buzz] [--fire]
"""
import argparse
import json
import urllib.request


def call(base: str, method: str, path: str, payload: dict | None = None) -> dict:
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = resp.read().decode()
        return json.loads(body) if body else {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8765")
    ap.add_argument("--buzzer-url", default="http://127.0.0.1:9999/buzz")
    ap.add_argument("--fire", action="store_true", help="fire one test action after reset")
    args = ap.parse_args()

    wiped = call(args.base, "DELETE", "/api/history")
    print(f"history wiped: {wiped}")
    call(args.base, "POST", "/api/monitoring/resume")
    call(args.base, "PUT", "/api/settings/personality", {"personality_id": "angry_chef"})
    print("monitoring resumed, personality reset to angry_chef")

    hooks = call(args.base, "GET", "/api/webhooks")
    buzzers = [h for h in hooks if h["url"] == args.buzzer_url]
    if not buzzers:
        hid = call(args.base, "POST", "/api/webhooks",
                   {"url": args.buzzer_url, "name": "desk-buzzer", "min_severity": 2})["id"]
        print(f"buzzer webhook registered (id {hid})")
    else:
        for extra in buzzers[1:]:
            call(args.base, "DELETE", f"/api/webhooks/{extra['id']}")
        call(args.base, "PATCH", f"/api/webhooks/{buzzers[0]['id']}",
             {"enabled": True, "min_severity": 2})
        print(f"buzzer webhook ok (id {buzzers[0]['id']})")

    if args.fire:
        call(args.base, "POST", "/api/actions/test?category=token_conservation&severity=2"
             "&message=Demo reset test firing")
        print("test action fired")
    print("demo state ready.")


if __name__ == "__main__":
    main()
