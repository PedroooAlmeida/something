# Gordon — the agent that watches *you* use agents

Computer-use agents watch a screen and act on it. **Gordon is computer use in
reverse**: it watches your screen while *you* drive Cursor, Claude, or any AI
coding tool — and coaches the one part no autocomplete fixes: **how you prompt**.

You type *"make this work"* into Cursor. Gordon's watcher OCRs the submission,
an evaluation model scores it against a six-category rubric, and ~3 seconds
later an angry chef pops over your editor and says, out loud:

> *"'Make this work'? That's an empty plate slid across the pass!"*

…followed by what actually matters: the diagnosis, the lesson, and a rewritten
prompt you can paste back in. Prompt well, and he grudgingly admits it — no
popup, no buzzer, just a quiet 90.

## Why a roast makes you a better (and cheaper) agent driver

- **Use less context.** The two most expensive habits in agent-assisted coding
  are dumping 3,000 lines to ask about one, and re-asking for whole files.
  Gordon's `token_conservation` and `context_management` categories catch both
  in the moment, and every verdict ships an `improved_prompt` showing the
  surgical version. Fewer wasted tokens, less context-window churn, faster
  agents.
- **Stay in control while prompting.** The voice is the point: an audible
  interrupt lands *while you still remember what you meant*, not in some weekly
  dashboard. Severity maps to real-world actions — `smart_light`,
  `desk_buzzer`, `bell_bot` — via webhooks, so bad habits have consequences you
  can hear.
- **Stay current.** A seeded frontier-knowledge base (web-verified dates +
  primary sources) means prompting for `componentWillMount` or
  `create-react-app` gets you roasted *with receipts* — release date and source
  URL included in the verdict.
- **It's fair.** Six scores (specificity, token conservation, frontier
  awareness, tool selection, context management, verification), one verdict,
  and genuinely good prompts score ≥ 80 with `should_interrupt: false`.

## Quickstart (macOS)

```bash
git clone <this repo> && cd <repo>
cp .env.example .env          # add ANTHROPIC_API_KEY (+ ELEVENLABS_API_KEY for voice)
./start.sh                    # engine + backend + overlay, one command
```

Then open **http://127.0.0.1:8765/** (landing + live dashboard) and run the
six-beat presenter demo:

```bash
./scripts/demo.sh             # ENTER-paced; --auto to self-run
```

Live capture instead of scripted events: `./start.sh --with-capture`
(grants macOS Screen Recording; runs in `--submit-only` privacy mode — it only
captures when you actually press send).

Missing keys degrade gracefully: no ElevenLabs → macOS system TTS; no engine →
the backend's rule-based mock keeps the pipeline alive.

## How it works

```
your screen (Cursor / Claude / terminal)
   │  OCR + submit detection            capture/   (Quartz + Vision, Anthropic classifier)
   ▼
POST /api/events                        backend/   (FastAPI + SQLite, dashboard, webhooks)
   │  GORDON_ENGINE_URL
   ▼
POST /evaluate                          src/gordon/ (engine: claude-opus-5 rubric, roast
   │                                       streamed roast-first; ElevenLabs voice with
   │                                       cache + system-TTS fallback; safety filters;
   │                                       anti-fabrication scrubber; knowledge citations)
   ▼
WS /ws/overlay ──► overlay popup + spoken roast     electron-shell/
             └──► dashboard, webhook actions (buzzer/light/bell)
```

Engine guarantees, enforced by tests: the roast is the first thing the model
streams (audio synthesis starts mid-stream); audio never blocks the verdict;
a safety filter runs before anything is spoken; any number/version/date not
present in supplied context is stripped (no invented facts); roasts stay ≤ 35
words and attack the decision, never the person.

## Repo layout / team split

| Folder | Owner | What lives here |
|---|---|---|
| `electron-shell/` | Person 1 | Always-on-top overlay, roast cards, audio playback; browser demo under `design_handoff_gordon_overlay/` |
| `capture/` | Person 2 | Screen watcher: OCR, submit detection, redaction, activity feed (`--submit-only` privacy mode) |
| `src/gordon/` | Person 3 | Evaluation engine: rubric, roasts, `improved_prompt`, personalities, ElevenLabs voice, safety, knowledge |
| `backend/` | Person 4 | Platform service: event API, SQLite, dashboard analytics, knowledge service, webhook action router |

## Integration reference

- Shared event JSON: PRD section 17, implemented in `backend/app/models.py`;
  engine contract + invariants in `CLAUDE.md`; component wiring in `HANDOFF.md`.
- Hosted platform: `https://gordon-platform.fly.dev` (docs at `/docs`) —
  local stack uses `http://127.0.0.1:8765`, and the overlay/dashboard
  auto-detect local vs hosted.
- Engine API: `POST /evaluate`, `POST /classify` (roastworthiness pre-gate),
  `GET /audio/{key}`, `GET /health` on `:8001`.
- Devices: `POST /api/webhooks` subscribes anything with an HTTP endpoint to
  violation events (severity-filtered) — desk buzzers, smart lights, bell bots.
