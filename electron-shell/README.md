# Gordon — desktop shell (frontend)

Electron app that runs the two Gordon surfaces as real desktop windows:

- **Overlay** (`overlay.html`) — frameless, transparent, always-on-top popup. Invisible
  while you code; appears in the screen corner when Gordon yells, then dismisses.
- **Kitchen** (`../design_handoff_gordon_overlay/Gordon.dc.html`) — the dashboard +
  Personalities + Settings & Privacy window, opened on demand.

## Run

```sh
./run.sh          # handles the Darwin 25 ad-hoc re-sign, then launches
```

Hotkeys: **⌥⌘G** opens the Kitchen · **⌥⌘Y** scores the clipboard and pops the overlay.

## Architecture — one data contract, clean seams

Everything flows through a single **verdict** object (`verdict-contract.js`):

```
   capture a prompt          scorePrompt(text)              overlay renders
  (teammate's job)   ──►   scorer.js -> verdict   ──►   overlay.html (verdict-driven)
```

The overlay renders **only** from a verdict. The scorer is the only thing that
produces one. That's the seam other people plug into.

## Who owns what

| Piece | File | Owner |
|---|---|---|
| Overlay + Kitchen UI, verdict rendering | `overlay.html`, `main.js`, `preload.js` | **Frontend (me)** |
| Verdict data shape | `verdict-contract.js` | Frontend — shared contract |
| Real scoring + **API key** | `scorer.js`, `.env` | **Abhay** — see below |
| Capturing the submitted prompt | (replaces the ⌥⌘Y stand-in in `main.js`) | Capture teammate |
| Firing physical devices on a verdict | (webhook, not built here) | Devices teammate |

### Scoring / API key — Abhay

`scorer.js` calls Claude (`claude-opus-4-8`, structured output → validated verdict).
It needs `ANTHROPIC_API_KEY`. **Until that's set it returns a realistic mock verdict**,
so the whole frontend runs and is buildable with zero changes.

To wire the real key:

```sh
cp .env.example .env      # then paste the key into .env (gitignored)
```

Launch logs `scoring mode: REAL (Claude)` or `MOCK` so you can tell which is active.

### Capture — teammate

Right now **⌥⌘Y** is a dev stand-in: it grabs clipboard text and calls `yell(text)`.
Real capture (detecting a prompt submitted in Cursor/terminal + screenshot) replaces
that trigger and calls the same `yell(capturedPrompt)` — nothing downstream changes.

## Notes

- `AUTO_HIDE_MS` in `overlay.html` — `0` = card stays until dismissed; `14000` = the
  real "yell then leave" behaviour.
- On launch the app scores a sample prompt so both windows are visibly running.
