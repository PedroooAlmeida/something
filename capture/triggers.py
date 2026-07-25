"""Local trigger rules over semantic events. No model — pure heuristics.

One rule fires per semantic event, highest priority first:
leak > thrash > repeat > lazy_prompt > vague_prompt. Paste and no_read are
separate semantic events and evaluated independently.
"""
import statistics
import threading

from . import redact, textutil
from .classifier import Classifier

CATEGORY = {
    "leak": "context_management",
    "token_dump": "token_conservation",
    "no_read": "verification",
    "repeat": "context_management",
    "thrash": "context_management",
    "lazy_prompt": "prompt_specificity",
    "vague_prompt": "prompt_specificity",
}

# Kinds where a same-kind repeat within cooldown escalates instead of suppressing.
ESCALATING = ("repeat", "thrash", "token_dump", "submission")


class TriggerEngine:
    def __init__(self, cfg, emitter, debug=False):
        self.cfg = cfg
        self.emitter = emitter
        self.debug = debug
        self.last_fire_ts = None
        self.kind_history = {}   # kind -> {"last_ts": float, "count": int}
        self.gate_lock = threading.Lock()   # classifier fires from its thread
        self.model = Classifier(cfg, self._fire_model, debug=debug)
        if self.model.enabled:
            self.model.start()
        elif debug:
            print("[gordon:model] disabled (no XAI_API_KEY or model_enabled=false)")

    def process(self, sem, app="", window_title=""):
        """Evaluate a semantic event; emit at most one roast event per sem."""
        rule = self._match(sem)
        if rule is not None:
            return self._fire(rule, sem, app, window_title)
        # Local rules didn't decide — hand the submission to the model.
        if (sem.kind == "submission" and self.model.enabled
                and not textutil.is_skippable(sem.data["text"])):
            self.model.submit(sem, app, window_title)
        return None

    # -- rules --------------------------------------------------------------

    def _match(self, sem):
        c = self.cfg
        d = sem.data
        if sem.kind == "paste":
            if d["size"] >= c.token_dump_min:
                sev = 3 if d["size"] >= c.token_dump_severe else 2
                return ("token_dump", sev,
                        f"Pasted {d['size']} chars into the composer in one go.")
            return None

        if sem.kind == "reading_ended":
            if (d["read_time_ms"] < c.no_read_ms
                    and d["response_len"] > c.no_read_response_len
                    and not d["scrolled"]):
                return ("no_read", 2,
                        f"Response was ~{d['response_len']} chars; replied in "
                        f"{d['read_time_ms'] / 1000:.1f}s without scrolling.")
            return None

        if sem.kind == "submission":
            text = d["text"]
            secrets = redact.find_secrets(text)
            if secrets:
                return ("leak", 3,
                        f"Prompt contains what looks like: {', '.join(secrets)}.")
            if textutil.is_affirmation(text):
                return None   # "ok" / "yes" — never roastable
            if d["submits_in_window"] >= c.thrash_count:
                recent = d["recent_texts"][-c.thrash_count:]
                sims = [textutil.jaccard(a, b)
                        for a, b in zip(recent, recent[1:])]
                if sims and statistics.mean(sims) >= c.thrash_similarity:
                    return ("thrash", 3,
                            f"{d['submits_in_window']} near-identical submits in "
                            f"{int(c.thrash_window_s)}s (mean similarity "
                            f"{statistics.mean(sims):.2f}). Rephrasing the same "
                            f"question is not debugging.")
            if d["similarity_to_prev"] > c.repeat_similarity:
                return ("repeat", 2,
                        f"Prompt is {d['similarity_to_prev']:.0%} similar to the "
                        f"previous one. Asking again louder does not add context.")
            if (d["dwell_ms"] < c.lazy_dwell_ms and len(text) < c.lazy_len):
                return ("lazy_prompt", 2,
                        f"{len(text)} chars composed in {d['dwell_ms'] / 1000:.1f}s. "
                        f"No file, no error, no expected behavior.")
            if (textutil.vagueness_hits(text) >= 1
                    and textutil.specificity_markers(text) == 0
                    and len(text) < 400):
                return ("vague_prompt", 2,
                        "Vague ask with zero specificity markers — no error text, "
                        "no file path, no expected output.")
        return None

    # -- gate + emit --------------------------------------------------------

    def _fire(self, rule, sem, app, window_title):
        kind, severity, evidence = rule
        return self._emit(kind, CATEGORY[kind], severity, evidence,
                          sem, app, window_title)

    def _fire_model(self, verdict, sem, app, window_title):
        """Called from the classifier thread with a qualifying verdict."""
        score = verdict["score"]
        severity = 3 if score < 25 else 2 if score < 45 else 1
        return self._emit("submission", verdict["category"], severity,
                          verdict["evidence"], sem, app, window_title,
                          score=score, confidence=verdict["confidence"])

    def _emit(self, kind, category, severity, evidence, sem, app,
              window_title, **extra):
        with self.gate_lock:
            now = sem.ts
            if (self.last_fire_ts is not None
                    and now - self.last_fire_ts < self.cfg.cooldown_s):
                self._log(f"suppressed {kind}: global cooldown")
                return None

            hist = self.kind_history.get(kind)
            if hist and now - hist["last_ts"] < self.cfg.kind_cooldown_s:
                if kind in ESCALATING:
                    severity = min(3, severity + 1)   # repetition is the joke
                    evidence += f" Offense #{hist['count'] + 1} in the last 10 minutes."
                else:
                    self._log(f"suppressed {kind}: same lesson within cooldown")
                    return None

            self.kind_history.setdefault(kind, {"last_ts": 0, "count": 0})
            self.kind_history[kind]["last_ts"] = now
            self.kind_history[kind]["count"] += 1
            self.last_fire_ts = now
            count = self.kind_history[kind]["count"]

        data = dict(sem.data)
        if "text" in data:
            data["text"] = redact.redact(data["text"])
        data.pop("recent_texts", None)   # don't persist the whole history

        event = {
            "kind": kind,
            "category": category,
            "severity": severity,
            "evidence": evidence,
            "ts": sem.ts,
            "app": app,
            "window_title": window_title,
            "trigger_source": sem.kind,
            "behavior": data,
            "offense_count": count,
            **extra,
        }
        return self.emitter.write(event)

    def _log(self, msg):
        if self.debug:
            print(f"[gordon:gate] {msg}")
