#!/usr/bin/env python3
"""Stand-in for the physical device: a tiny webhook receiver that 'buzzes'
(prints + system beep) whenever Gordon dispatches a prompt_violation.

Usage:
  python scripts/buzzer_receiver.py            # listens on :9999
  curl -X POST localhost:8765/api/webhooks -H 'Content-Type: application/json' \
       -d '{"url": "http://127.0.0.1:9999/buzz", "name": "desk-buzzer", "min_severity": 2}'

Swap the buzz() body for GPIO / smart-light / servo calls on real hardware —
the adapter contract is just this webhook payload.
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 9999


def buzz(payload: dict):
    print("\a", end="", flush=True)  # terminal bell
    print(f"🔴 BZZZT!  severity={payload.get('severity')} "
          f"category={payload.get('category')} :: {payload.get('message')}")


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            payload = {}
        buzz(payload)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"buzzed": true}')

    def log_message(self, *args):  # silence default request logging
        pass


if __name__ == "__main__":
    print(f"desk buzzer listening on http://127.0.0.1:{PORT}/buzz")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
