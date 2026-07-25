"""Model roast classifier: xAI call on submissions the local rules didn't decide.

Runs in a daemon thread so the ~400ms API call never blocks the 10Hz loop.
Verdict shape per capture.md: {score, category, evidence, confidence}.
"""
import json
import os
import queue
import re
import threading
import urllib.error
import urllib.request

XAI_URL = "https://api.x.ai/v1/chat/completions"

CATEGORIES = {
    "prompt_specificity", "context_management", "verification",
    "token_conservation", "delegation",
}

SYSTEM_PROMPT = """\
You judge the craft of prompts a developer sends to an AI coding assistant.
Score the prompt 0-100 for how well it uses the assistant (100 = precise,
contextual, verifiable ask; 0 = lazy, vague, wasteful).

Consider the behavior metrics: dwell_ms (time composing), paste_sizes,
similarity_to_prev, submits_in_window.

Reply with ONLY a JSON object, no markdown fences:
{"score": <int 0-100>, "category": <one of "prompt_specificity",
"context_management", "verification", "token_conservation", "delegation">,
"evidence": <string, must cite a concrete observed feature of THIS prompt or
its metrics — never invent a flaw that is not present>, "confidence": <float 0-1>}"""


def load_env(path=".env"):
    """Tiny .env loader — no dependency. Existing env vars win."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


class Classifier(threading.Thread):
    """Worker thread: queue of submissions in, gated verdicts out via fire_cb."""

    def __init__(self, cfg, fire_cb, debug=False):
        super().__init__(daemon=True, name="gordon-classifier")
        load_env()
        self.cfg = cfg
        self.fire_cb = fire_cb   # fire_cb(verdict, sem, app, window_title)
        self.debug = debug
        self.api_key = os.environ.get("XAI_API_KEY", "")
        self.q = queue.Queue(maxsize=4)

    @property
    def enabled(self):
        return bool(self.api_key) and self.cfg.model_enabled

    def submit(self, sem, app, window_title):
        try:
            self.q.put_nowait((sem, app, window_title))
        except queue.Full:
            self._log("queue full, dropping submission")

    def run(self):
        while True:
            sem, app, window_title = self.q.get()
            try:
                v = self.classify(sem.data["text"], sem.data, app)
            except Exception as e:
                self._log(f"classify failed: {type(e).__name__}: {e}")
                continue
            if v is None:
                continue
            self._log(f"verdict score={v['score']} conf={v['confidence']} "
                      f"cat={v['category']}")
            if (v["score"] < self.cfg.model_score_threshold
                    and v["confidence"] > self.cfg.model_confidence_min):
                self.fire_cb(v, sem, app, window_title)

    # -- API call -----------------------------------------------------------

    def classify(self, text, behavior, app):
        """One xAI call. Returns validated verdict dict or None."""
        metrics = {k: behavior.get(k) for k in
                   ("dwell_ms", "paste_sizes", "similarity_to_prev",
                    "submits_in_window")}
        user = (f"App: {app}\nBehavior metrics: {json.dumps(metrics)}\n"
                f"Prompt:\n{text[:self.cfg.model_max_text]}")
        body = json.dumps({
            "model": self.cfg.xai_model,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                         {"role": "user", "content": user}],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }).encode()
        req = urllib.request.Request(XAI_URL, data=body, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        })
        with urllib.request.urlopen(req, timeout=self.cfg.model_timeout_s) as r:
            out = json.loads(r.read())
        raw = out["choices"][0]["message"]["content"]
        return self._parse(raw)

    def _parse(self, raw):
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            return None
        try:
            v = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
        if not isinstance(v.get("evidence"), str) or not v["evidence"].strip():
            return None   # evidence is required — no evidence, no roast
        try:
            score = int(v["score"])
            conf = float(v.get("confidence", 0.0))
        except (KeyError, TypeError, ValueError):
            return None
        cat = v.get("category", "")
        return {"score": max(0, min(100, score)),
                "confidence": max(0.0, min(1.0, conf)),
                "category": cat if cat in CATEGORIES else "prompt_specificity",
                "evidence": v["evidence"].strip()}

    def _log(self, msg):
        if self.debug:
            print(f"[gordon:model] {msg}")
