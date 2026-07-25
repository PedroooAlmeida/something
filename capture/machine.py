"""Screen state machine: turns OCR/diff ticks into semantic events.

States: IDLE -> COMPOSING -> (SUBMITTED) -> STREAMING -> READING -> COMPOSING ...

Submit detection without a hook: composer goes non-empty -> empty, corroborated
by the conversation region changing within `submit_corroborate_s`. Escape or
navigation empties the composer too, but without the new-block corroboration
no submission is emitted.
"""
from collections import deque
from dataclasses import dataclass

from .textutil import jaccard

IDLE = "IDLE"
COMPOSING = "COMPOSING"
STREAMING = "STREAMING"
READING = "READING"


@dataclass
class SemEvent:
    kind: str      # paste | submission | response_done | reading_ended
    ts: float
    data: dict


class Machine:
    def __init__(self, cfg, read_conversation=None):
        self.cfg = cfg
        # Callback OCRs the conversation band on demand (submit / done ticks only).
        self.read_conversation = read_conversation or (lambda: "")
        self.state = IDLE
        self.composer = ""
        self.compose_start = None
        self.paste_sizes = []
        self.pending_submit = None       # (ts, text, compose_start, paste_sizes)
        self.last_conv_change = None
        self.conv_len_at_submit = 0
        self.submit_ts = None
        self.last_submitted = ""
        self.submits = deque()           # (ts, text) within thrash window
        self.done_ts = None
        self.response_len = 0
        self.scrolled = False

    def feed(self, ts, composer_text=None, conv_changed=False, scrolled=False):
        """One tick. composer_text=None means 'no new OCR reading this tick'."""
        events = []
        if conv_changed:
            self.last_conv_change = ts
        if scrolled and self.state == READING:
            self.scrolled = True

        if composer_text is not None:
            self._composer_tick(ts, composer_text, events)

        self._check_submit(ts, events)
        self._check_done(ts, events)
        return events

    # -- internals ----------------------------------------------------------

    def _composer_tick(self, ts, txt, events):
        prev = self.composer
        if txt and not prev:
            # Typing while the assistant still streams: the response is done
            # as far as the user cares — finalize it so the read gets measured.
            if self.state == STREAMING and self.submit_ts is not None:
                events.append(self._finalize_response(ts))
            # Composing begins. If we were reading a response, that read ends now.
            if self.state == READING and self.done_ts is not None:
                events.append(SemEvent("reading_ended", ts, {
                    "read_time_ms": int((ts - self.done_ts) * 1000),
                    "response_len": self.response_len,
                    "scrolled": self.scrolled,
                }))
                self.done_ts = None
            self.state = COMPOSING
            self.compose_start = ts
            self.paste_sizes = []
            if len(txt) >= self.cfg.paste_delta:   # appeared fully-formed: a paste
                self.paste_sizes.append(len(txt))
                events.append(SemEvent("paste", ts, {"size": len(txt)}))
        elif txt and prev:
            delta = len(txt) - len(prev)
            if delta >= self.cfg.paste_delta:
                self.paste_sizes.append(delta)
                events.append(SemEvent("paste", ts, {"size": delta}))
        elif prev and not txt:
            # Composer emptied — submission candidate, awaiting corroboration.
            self.pending_submit = (ts, prev, self.compose_start or ts,
                                   list(self.paste_sizes))
        self.composer = txt

    def _check_submit(self, ts, events):
        if not self.pending_submit:
            return
        pts, text, cstart, pastes = self.pending_submit
        # Conversation changed at (or just before — OCR lag) the empty tick.
        corroborated = (self.last_conv_change is not None
                        and self.last_conv_change >= pts - 0.3)
        if corroborated:
            sim = jaccard(text, self.last_submitted) if self.last_submitted else 0.0
            self.submits.append((pts, text))
            while self.submits and pts - self.submits[0][0] > self.cfg.thrash_window_s:
                self.submits.popleft()
            events.append(SemEvent("submission", pts, {
                "text": text,
                "dwell_ms": int((pts - cstart) * 1000),
                "paste_sizes": pastes,
                "similarity_to_prev": round(sim, 3),
                "submits_in_window": len(self.submits),
                "recent_texts": [t for _, t in self.submits],
            }))
            self.last_submitted = text
            self.submit_ts = pts
            self.state = STREAMING
            self.conv_len_at_submit = len(self.read_conversation() or "")
            self.pending_submit = None
        elif ts - pts > self.cfg.submit_corroborate_s:
            # Cleared without a new block: escape / navigation, not a submit.
            self.pending_submit = None
            if self.state == COMPOSING:
                self.state = IDLE

    def _check_done(self, ts, events):
        if self.state != STREAMING or self.submit_ts is None:
            return
        if self.last_conv_change is None or ts - self.submit_ts < 1.0:
            return
        if ts - self.last_conv_change >= self.cfg.stream_settle_s:
            events.append(self._finalize_response(ts))

    def _finalize_response(self, ts):
        conv = self.read_conversation() or ""
        self.response_len = max(0, len(conv) - self.conv_len_at_submit)
        # Response finished when growth stopped, not when we noticed.
        self.done_ts = self.last_conv_change or ts
        self.scrolled = False
        self.state = READING
        return SemEvent("response_done", ts,
                        {"response_len": self.response_len})
