# Live Roast Triggers

Service watches the screen continuously and fires an event the moment it sees something worth roasting. Nothing else.

---

## The problem

Streaming frames to a vision model is too slow and too expensive to run live. Polling on a timer means we notice things seconds after they happen.

So: **cheap local perception at high frequency, model only on semantic change.** Each layer wakes the next only when something actually happened.

```
10 Hz  grab + hash        ~2ms   local, free   ← 90% of frames die here
 ~4 Hz OCR changed region ~35ms  local, free   ← only on pixel change
 ~2 Hz state machine      <1ms   local, free
 rare  classifier        ~400ms  model         ← only on transitions
```

At rest this costs one 64-bit compare every 100ms.

---

## Loop

```python
while True:
    app = frontmost_app()                       # 2Hz, Quartz
    if app not in ALLOWLIST:
        sleep(0.5); continue                    # no capture at all

    frame = grab(app.bounds)                    # mss, ~2ms
    h = dhash(downscale(frame, 320, 200))
    if hamming(h, last_h) < 3:                  # nothing moved
        sleep(0.1); continue

    roi = changed_cell(frame, last_frame)       # 8x6 grid diff → where
    text = ocr(crop(frame, roi))                # Apple Vision, fast mode
    for ev in machine.feed(roi, text):          # transitions only
        bus.put(ev)
```

**`changed_cell` is what makes it cheap.** Localizing the change means OCR runs on a 900×180 strip instead of the whole screen. It also carries most of the meaning:

| Region changed | Means |
|---|---|
| bottom band, small delta | typing |
| bottom band, huge delta in one frame | paste |
| middle band growing downward | assistant streaming |
| everything shifts vertically | scrolling / reading |

---

## State machine

```
IDLE ──text appears──► COMPOSING ──delta>200ch──► PASTED
  ▲                        │
  │      composer empties + new block above
  │                        ▼
  │                    SUBMITTED ──► STREAMING ──growth stops 1.5s──► DONE
  │                                                                    │
  └──────────────────── READING ◄──────────────────────────────────────┘
```

Submit detection with no hook: **composer goes non-empty → empty within one or two frames, and a new text block appears above.** True regardless of Enter, click, shortcut, or programmatic submit. Require the new-block corroboration or escape/navigation looks like a submit.

The machine tracks, across transitions: `dwell_ms` (first keystroke → submit), `paste_size`, `response_len`, `read_time_ms` (DONE → next keystroke), `scrolled`, `similarity` vs the previous submission.

---

## Triggers

Two kinds. Local triggers need no model at all.

**Local — fire immediately, zero latency:**

| Condition | Trigger |
|---|---|
| paste ≥ 2000 chars | `token_dump` |
| `read_time_ms < 8000` and `response_len > 1200` and not `scrolled` | `no_read` |
| `similarity(prompt, prev) > 0.85` | `repeat` |
| 3 submits in 90s, rising similarity | `thrash` |
| `dwell_ms < 2000` and `len < 40` | `lazy_prompt` |
| secret regex hits composer | `leak` |

These are the good demo moments — the user typed nothing new and Gordon reacts anyway.

**Model — on SUBMITTED, when local rules don't already decide:**

```python
async def on_submit(text, behavior, screen):
    if is_skippable(text):                      # "ok", "yes", answering a question,
        return                                  # pure error paste (that's good behavior)

    v = await classify(text, behavior, screen)  # ~400ms, small model, forced JSON
    if v.score < 55 and v.confidence > 0.6:
        fire(v)
```

`classify` returns `{score, category, evidence, confidence}`. `evidence` is required and must cite an observed feature — it stops the model roasting a prompt for a flaw it doesn't have.

**Gate before firing anything:** 45s cooldown, and skip if the same category fired in the last 10 minutes unless it's a repeat offense — in which case severity goes *up*, because the repetition is the joke.

---

## Speculation (the latency answer)

We can see the draft while it's being typed, so we don't wait for submit.

```python
on_composer_pause(700ms):                       # user stopped to think
    if len(draft) > 25 and changed_15pct_since_last_score():
        v = await classify(draft, ...)          # background
        if v.score < 55: cache[hash(draft)] = v
```

On SUBMITTED, check the cache first. Hit → fire in ~50ms instead of ~400ms. Cap at 3 speculative calls per composition; invalidate if the draft changes materially after scoring.

---

## Emitted event

```jsonc
{
  "kind": "no_read",           // or token_dump | repeat | thrash | lazy_prompt | leak | submission
  "ts": 1753387200.4,
  "app": "Claude",
  "text": "make this work",    // redacted
  "score": 31,
  "category": "verification",
  "evidence": "Response 1840 chars, replied in 4.2s, no scroll.",
  "severity": 2
}
```

Onto an in-process bus, out over WS. Consumers (overlay, voice, webhook) are somebody else's problem.

---

## Build order

1. Focus gate + grab + hash. Confirm idle cost is near zero.
2. OCR on one target app. Hand-calibrate the composer rect (drag a box, save to config) — auto-discovery is the biggest risk and the manual version takes five minutes.
3. State machine. Record a session to frames, replay it, assert the transition sequence. This is the test suite.
4. Local triggers. Demos on its own, no model.
5. Model trigger on submit.
6. Speculation, last — it's an optimization.

---

## Notes

- macOS Screen Recording permission needs an app restart after granting. Grant it on the demo machine early.
- `mss` for grabbing. `ScreenCaptureKit` only if 10Hz measurably struggles.
- Frames stay in a RAM ring buffer, never disk. Redact OCR text before it hits the bus.
- Non-allowlisted app means no capture happens at all — absence, not a filter.
