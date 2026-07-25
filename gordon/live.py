"""Live activity feed: watch the screen, summarize what the user is doing
through Grok, emit JSON events.

Loop: grab frontmost allowlisted window at 2Hz -> on change + every
summary_interval_s, OCR the window -> one Grok call -> JSON event into
roast_events/ and onto stdout. Run: python -m gordon.live [--debug]
"""
import argparse
import json
import sys
import time
import urllib.request

import numpy as np
import Quartz

from . import config as config_mod
from . import redact
from .classifier import XAI_URL, load_env
from .emitter import Emitter
from .ocr import ocr
from .screen import Grabber, frontmost

import os

SYSTEM_PROMPT = """\
You watch a developer's screen through OCR text and narrate what they are doing.
Input: frontmost app, window title, OCR text of the ENTIRE screen — it may
contain several windows and panes at once (editor, AI chat, terminal, browser).
The OCR is noisy; infer structure from content.

Reply with ONLY a JSON object, no markdown fences:
{"activity": <dominant one of "coding", "ai_chat", "terminal", "browsing",
"reading", "debugging", "writing", "other">,
"summary": <one or two sentences, present tense, covering EVERY distinct thing
visible on screen — every chat, file, command, page. Concrete, cite what is
actually there. Quote short prompts the user typed to AI assistants verbatim>,
"details": <short string: all file names, commands, prompts, topics, errors seen>}"""


class LiveFeed:
    def __init__(self, cfg, debug=False):
        load_env()
        self.cfg = cfg
        self.debug = debug
        self.api_key = os.environ.get("XAI_API_KEY", "")
        if not self.api_key:
            sys.exit("[gordon] XAI_API_KEY missing (.env or env)")
        self.grabber = Grabber()
        self.emitter = Emitter(cfg.events_dir)
        self.prev_gray = None
        self.changed_since_summary = False
        self.last_summary_ts = 0.0
        self.last_summary = ""

    # -- grok ---------------------------------------------------------------

    def summarize(self, app, title, text):
        user = (f"Frontmost app: {app}\nWindow title: {title}\n"
                f"Previous summary (avoid repeating verbatim): {self.last_summary}\n"
                f"Full-screen OCR:\n{text}")
        body = json.dumps({
            "model": self.cfg.xai_model,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                         {"role": "user", "content": user}],
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
        }).encode()
        req = urllib.request.Request(XAI_URL, data=body, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        })
        with urllib.request.urlopen(req, timeout=self.cfg.model_timeout_s) as r:
            out = json.loads(r.read())
        v = json.loads(out["choices"][0]["message"]["content"])
        if not isinstance(v.get("summary"), str) or not v["summary"].strip():
            return None
        return {"activity": str(v.get("activity", "other")),
                "summary": v["summary"].strip(),
                "details": str(v.get("details", ""))}

    # -- loop ---------------------------------------------------------------

    def run(self):
        print("[gordon] live feed: ENTIRE screen, all apps")
        print(f"[gordon] summarizing every ~{self.cfg.summary_interval_s:.0f}s "
              f"on change -> {self.cfg.events_dir}/")
        while True:
            start = time.time()
            try:
                self.tick(start)
            except Exception as e:
                if self.debug:
                    print(f"[gordon:err] {type(e).__name__}: {e}")
                self.prev_gray = None
            time.sleep(max(0.0, 0.5 - (time.time() - start)))

    def tick(self, now):
        app, _bounds, title = frontmost()   # context for the event only
        # Entire screen (all displays), regardless of what app is frontmost.
        gray = self.grabber.grab(self.grabber.sct.monitors[0])
        if self.prev_gray is not None and gray.shape == self.prev_gray.shape:
            if np.abs(gray - self.prev_gray).mean() > 1.0:
                self.changed_since_summary = True
        else:
            self.changed_since_summary = True
        self.prev_gray = gray

        if (self.changed_since_summary
                and now - self.last_summary_ts >= self.cfg.summary_interval_s):
            self.changed_since_summary = False
            self.last_summary_ts = now
            text = redact.redact(ocr(self.grabber.crop((0.0, 0.0, 1.0, 1.0)),
                                     fast=True))[:self.cfg.live_max_text]
            if self.debug:
                print(f"[gordon:ocr] {app}: {len(text)} chars")
            if len(text.strip()) < 20:
                return
            v = self.summarize(app, title, text)
            if v is None:
                return
            self.last_summary = v["summary"]
            self.emitter.write({
                "kind": "activity",
                "ts": now,
                "app": app,
                "window_title": title,
                **v,
            })


def main():
    ap = argparse.ArgumentParser(description="Gordon live activity feed")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()
    if not Quartz.CGPreflightScreenCaptureAccess():
        Quartz.CGRequestScreenCaptureAccess()
        sys.exit("[gordon] grant Screen Recording permission, restart terminal, rerun")
    cfg = config_mod.load(args.config)
    try:
        LiveFeed(cfg, debug=args.debug).run()
    except KeyboardInterrupt:
        print("\n[gordon] stopped")


if __name__ == "__main__":
    main()
