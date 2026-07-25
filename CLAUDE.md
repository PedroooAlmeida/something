# CLAUDE.md — Gordon Engine (Person 3)

Hackathon build. Python. You are building **one component of a four-person system**:
the evaluation + voice service. Speed and demo reliability beat completeness.

## What this component does

Takes a captured prompt (what a developer typed into an AI coding tool), scores how
badly they used the tool, generates an in-character roast, synthesizes it as speech
via ElevenLabs, and returns structured JSON.

**In scope:** rubric, structured model output, roast generation, prompt rewriting,
personality prompts, frontier-knowledge retrieval, voice generation, safeguards.

**NOT in scope — do not build these, other people own them:**
- Desktop overlay / UI / animations (Person 1)
- Browser extension / screen capture (Person 2)
- Database, dashboard, webhooks, hardware (Person 4)

If a task seems to require one of those, stub it and move on.

---

## Stack

- Python 3.11+
- FastAPI + uvicorn (service)
- httpx (async HTTP — used for ElevenLabs)
- pydantic v2 (schemas)
- openai SDK (evaluation model — **isolated behind one function so it can be swapped**)
- pytest
- Dependencies via `pyproject.toml`. `uv` if available, else pip.

No database. No ORM. No Docker. No auth. Cache is files on disk.

---

## Layout

```
src/gordon/
  config.py         env vars, constants, paths
  schemas.py        CaptureEvent, Evaluation, EngineResponse
  personalities.py  registry: style_note, voice_id, severity -> voice settings
  rubric.py         SYSTEM_PROMPT + build_user_message()
  llm.py            stream_llm() — THE ONLY place a provider SDK is imported
  parsing.py        incremental roast extraction, JSON recovery
  safety.py         banned-term filter, anti-fabrication scrubber
  knowledge.py      seeded release records + keyword match
  voice.py          ElevenLabs synth, cache, fallback chain, prewarm
  engine.py         orchestration — evaluate()
  api.py            FastAPI routes
  harness.py        CLI: run fixture prompts, print score table
tests/
  fixtures/prompts.json
data/
  releases.json     seeded frontier-knowledge records
audio_cache/        gitignored
```

Keep modules small. `engine.py` orchestrates and contains no prompt text, no HTTP
calls, and no regexes.

---

## Contract — do not change without telling the team

Input (from Person 2):

```json
{"event_id":"uuid","timestamp":"...","source":"chat_application",
 "application":"...","prompt_text":"Make this work","selected_model":"unknown",
 "screenshot_path":"/tmp/x.png","session_id":"...","personality_id":"angry_chef"}
```

Output (to Person 1 and Person 4):

```json
{"roast":"...","overall_score":31,"primary_category":"prompt_specificity",
 "category_scores":{"prompt_specificity":15,"token_conservation":80,
   "frontier_awareness":70,"tool_selection":60,"context_management":25,
   "verification":20},
 "diagnosis":"...","lesson":"...","improved_prompt":"...","severity":2,
 "should_interrupt":true,"personality_id":"angry_chef","voice_id":"...",
 "audio_url":"/audio/<key>","audio_cache_key":"...","audio_status":"streaming",
 "action":"desk_buzzer","timing_ms":{"roast_ready":900,"total":2100}}
```

`audio_status` ∈ `cached | streaming | fallback_system_tts | unavailable`.
`category_scores` always contains all six keys.

---

## Invariants — violating these breaks the demo

1. **`roast` is the first key the model emits.** Audio synthesis starts the moment
   its closing quote arrives, while the rest of the JSON is still streaming.
2. **Audio never blocks the response.** If synthesis fails, return the JSON with
   `audio_status: "unavailable"`. The overlay must always appear.
3. **Safety filter runs before synthesis, never after.** Nothing that fails the
   filter is ever sent to ElevenLabs.
4. **No invented facts.** Any number, percentage, version string, or date in the
   output must appear in the supplied context, or the sentence gets stripped.
5. **Roast ≤ 35 words, ≤ 2 sentences.** It is spoken aloud.
6. **Attack the decision, never the person.** No identity, appearance, or
   intelligence-as-a-trait content, ever.
7. **Original synthetic voice only.** Never clone or imitate a real person's voice.

---

## Commands

```bash
uv sync                                  # or: pip install -e .
cp .env.example .env                     # fill in keys
uvicorn gordon.api:app --port 8001 --reload
python -m gordon.harness                 # run all fixture prompts, print table
python -m gordon.harness --prewarm       # cache demo audio
pytest -q
```

Health check at `GET /health` reports whether keys and voice IDs are configured.

---

## Build order

Work through these in order. **Do not start a milestone until the previous one's
acceptance criteria pass.** Ask me before skipping ahead.

### M0 — skeleton
Package layout, `pyproject.toml`, `.env.example`, config module reading
`OPENAI_API_KEY`, `ELEVENLABS_API_KEY`, `VOICE_CHEF`, `VOICE_PROF`, `EVAL_MODEL`.
`/health` returns config status.
**Accept:** server starts, `/health` 200s with keys reported as missing.

### M1 — thin slice, end to end
Hardcode input `"Make this work."`. LLM call → JSON parse → roast extracted →
ElevenLabs → mp3 on disk → served at `/audio/{key}`. Minimal rubric. One personality.
**Accept:** `POST /evaluate` returns valid JSON and the mp3 plays a real sentence
about the real prompt.

*This is the highest-risk milestone. If it isn't done in the first hour, tell me.*

### M2 — test harness
`tests/fixtures/prompts.json`: 20 bad prompts + 3 genuinely good ones, each with an
`expected_category`. `harness.py` runs them all and prints a table (prompt, score,
primary category, roast, word count). Text only, no audio, concurrent.
**Accept:** one command grades all 23 and prints in under ~60s.

### M3 — the rubric (the actual product — most of your time goes here)
Iterate on `SYSTEM_PROMPT` against the harness until:
- every roast names something concrete from that specific prompt
- primary category is correct on ≥18/20 bad prompts
- all 3 good prompts score ≥80 and set `should_interrupt: false`
- no roast exceeds 35 words
- `improved_prompt` is obviously better than the original in every case

Temperature ~0.9 — jokes need variance. Test: if a roast could be pasted under a
different prompt and still fit, it fails.
**Accept:** harness output meets all five bars.

### M4 — second personality
Registry-driven. Same engine, same scores, same lesson; different `style_note`,
`voice_id`, and severity→voice-settings map. Recommend Disappointed Professor —
slow, quiet, high stability — for maximum contrast with the chef.
**Accept:** identical input to both personalities gives identical
`category_scores` and different `roast` + audio.

### M5 — safeguards
`safety.py`:
- banned-term regex on roast text, pre-synthesis
- anti-fabrication scrubber: extract every number/percentage/version/date from the
  output; if not present in supplied context, drop that sentence and log it
**Accept:** unit tests cover both; a deliberately fabricated `"40% faster"` claim
is stripped.

### M6 — frontier knowledge (minimum viable)
`data/releases.json`: 10 records — technology, what_changed, release_date, source_url,
old_option, new_option. Keyword match against prompt text; inject matches into
context with an instruction to cite only from them, with date and source.

**No embeddings, no vector DB, no live RSS.** Write the importer as a stub with a
comment. **This is the cut line** — if we're behind schedule, skip M6 entirely and
tell me so I can hand it to Person 4.
**Accept:** a prompt naming an outdated technology produces a roast citing the newer
option with its date and source URL.

### M7 — freeze
Prewarm demo audio. Test fallback by unsetting `ELEVENLABS_API_KEY` mid-run and
confirming JSON still returns. Final harness run. No rubric changes after this.

---

## Conventions

- `async` throughout; never block the event loop (no `requests`, no `time.sleep`).
- Type hints on every public function. Pydantic models for all boundaries.
- All prompt text lives in `rubric.py` and `personalities.py`. Never inline a
  prompt string anywhere else.
- All tunable numbers in `config.py` as module constants. No magic numbers.
- Log timings for roast-ready and total on every request.
- Never `except: pass`. Log the exception, degrade gracefully, continue.
- Print statements are fine over logging config. It's a hackathon.

## Testing

- Unit tests must not hit the network. Mock `stream_llm` and the httpx client.
- `test_parsing.py` must verify the roast extractor returns `None` on a partial
  stream and the correct string once the closing quote arrives — including a roast
  containing escaped quotes.
- The harness is not pytest; it hits the real model and is run by hand.

## Gotchas

- **Verify the ElevenLabs model ID and endpoint against current docs before
  hardcoding.** Model names change; a Flash-class model is the low-latency tier.
- `speed` may or may not be accepted inside `voice_settings` on this account tier.
  If the API 422s, drop it and use `style` instead.
- ElevenLabs streams audio; write chunks to a `.part` file and rename on success so
  a failed request never leaves a truncated mp3 in the cache.
- Cache key must hash text + voice_id + voice settings + model ID. Changing voice
  settings must produce a new key or you'll serve stale audio during tuning.
- `.env` and `audio_cache/` are gitignored. Never commit a key.
- Screenshots go to the model as base64 image content. Skip the image if the path
  doesn't exist rather than erroring.

## When in doubt

Ask before: changing the JSON contract, adding a dependency, adding a service or
process, or building anything in the "not in scope" list. Everything else, just build
it and tell me what you did.
