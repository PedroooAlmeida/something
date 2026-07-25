# Handoff — merged capture + engine branch

Branch `feature/gordon-handoff` = `feature/gordon-engine` (Person 3, evaluation +
voice service) merged with `feat/screen-capture-event` (Person 2, screen capture).

## Layout

```
src/gordon/      engine service (FastAPI) — installed package `gordon`
capture/         screen-capture component (was top-level `gordon/` on the capture
                 branch; renamed to avoid shadowing the installed engine package.
                 Internal relative imports unchanged; scripts/simulate.py updated.)
scripts/bridge.py   LOCAL DEBUG ONLY — capture -> engine directly, skipping the
                    platform. Demo path: backend/scripts/capture_bridge.py
                    (capture -> /api/events); backend calls /evaluate itself via
                    GORDON_ENGINE_URL, overlay/dashboard/buzzer fire downstream.
                    Hosted backend reaching a local engine: `ngrok http 8001`
                    and set GORDON_ENGINE_URL to the ngrok URL.
data/releases.json  frontier-knowledge records (web-verified dates + sources)
tests/           engine unit tests (72, no network) + fixtures
```

## Run the full pipeline

```bash
# 1. engine (needs .env — see .env.example; ANTHROPIC_API_KEY + ELEVENLABS_API_KEY)
uv sync
uv run uvicorn gordon.api:app --port 8001

# 2. capture (separate deps — pyobjc/Vision etc.)
#    Model calls are Anthropic (claude-opus-5) — was Grok/xAI on the original
#    branch. Reads ANTHROPIC_API_KEY from the same root .env as the engine.
python -m venv .venv-capture && . .venv-capture/bin/activate
pip install -r capture/requirements.txt
python -m capture.main            # or: python -m capture.live --debug

# 3. bridge (engine venv)
uv run python scripts/bridge.py
```

## API surface (for Person 4)

| Route | In | Out |
|---|---|---|
| `POST /evaluate` | `CaptureEvent` JSON (contract in CLAUDE.md) | `EngineResponse` JSON — roast, six category scores, `audio_url`, timings, `source: {text, date, confidence, url} \| null` (set when a knowledge record informed the verdict) |
| `POST /classify` | same `CaptureEvent` JSON | `{roastworthy, confidence, reason, category_hint}` pre-gate; never 500s |
| `GET /audio/{key}` | 24-hex key from `audio_cache_key` | mp3/m4a (long-polls up to 10s while synthesis finishes) |
| `GET /health` | — | key/voice config status |

Event mapping (bridge does this; Person 4 can inline it): capture event
`{kind, category, severity, evidence, ts, iso, app, window_title, behavior{text}, event_id}`
→ engine `CaptureEvent{event_id, timestamp: iso, application: app, prompt_text: behavior.text || evidence, session_id: window_title, source: "screen_capture"}`.

## Known deviations / open items for the team

1. `improved_prompt` fabrication check is detect-and-log, not strip (stripping
   sentences from a rewritten prompt breaks it) — deviation from invariant 4.
2. Knowledge citations: release date goes in roast/diagnosis, source URL in
   diagnosis only (a spoken URL fails the 35-word spoken-roast rule).
3. `POST /classify` + `ClassifierVerdict` are additive surface beyond the spec'd
   contract (user-requested); /evaluate contract untouched.
4. Voice settings use severity 2 at synthesis time — severity streams after the
   roast, and invariant 1 (synth starts at roast close-quote) wins.
5. `action` values (per Person 4's platform enum): severity 1 -> `smart_light`,
   2 -> `desk_buzzer`, 3 -> `bell_bot`; `none` when not interrupting. Mapping
   lives in config.ACTION_BY_SEVERITY — confirm 2/3 assignment is as intended.
6. ElevenLabs free tier: only some premade voices work via API (Adam + Daniel
   configured); library voices 402.
