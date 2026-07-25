# Gordon — Platform Service (Person 4)

**Hosted: `https://gordon-platform.fly.dev`** (WS: `wss://gordon-platform.fly.dev/ws/overlay`).
Deploys via `flyctl deploy` from this folder (Dockerfile + fly.toml, SQLite on a 1GB volume).

Backend for Gordon: event API, SQLite storage, dashboard analytics, frontier-knowledge
service, and the webhook action router. Includes a rule-based **mock evaluator** so the
entire pipeline works end-to-end before Person 3's intelligence engine exists.

## Run

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8765 --reload
```

Smoke-test the whole pipeline with the PRD demo scenarios:

```bash
python scripts/send_mock_events.py            # in a second terminal
```

Optional desk-buzzer stand-in (webhook receiver):

```bash
python scripts/buzzer_receiver.py             # listens on :9999
curl -X POST localhost:8765/api/webhooks -H 'Content-Type: application/json' \
     -d '{"url": "http://127.0.0.1:9999/buzz", "name": "desk-buzzer", "min_severity": 2}'
```

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `GORDON_ENGINE_URL` | *(unset)* | Person 3's engine endpoint. Unset → built-in mock evaluator. On error → mock fallback, demo keeps running. |
| `GORDON_ENGINE_TIMEOUT` | `8` | Seconds before falling back to mock. |
| `GORDON_DB` | `backend/gordon.db` | SQLite path. |

## Integration contract

Shared event format is PRD section 17, exactly.

### Person 2 — capture service / extension
`POST /api/events` with the capture event. Response includes the evaluation, plus a
`redactions` list if secrets/PII were stripped before storage. When monitoring is
paused, returns `{"status": "paused", "evaluated": false}` — nothing is stored.

### Person 3 — intelligence engine
Two options (pick one):
1. **Pull (preferred):** expose `POST /evaluate` taking the capture event and returning
   the evaluation JSON; we set `GORDON_ENGINE_URL` to it.
2. **Push:** `POST /api/evaluations/{event_id}` with a finished evaluation for an event
   we already stored.

### Person 1 — overlay + dashboard
- Connect a WebSocket to `ws://127.0.0.1:8765/ws/overlay`. Every scored prompt arrives as
  `{"type": "coaching_response", "event": {...}, "evaluation": {...}}`.
- Dashboard data: `GET /api/dashboard/summary`, `/api/dashboard/history?days=7`,
  `/api/dashboard/daily` (the "you were yelled at 11 times" text block).
- Pause button: `POST /api/monitoring/pause` / `resume`, state at `GET /api/monitoring/status`.

### Devices (buzzer / light / servo / Slack)
Register a webhook; it receives the PRD section 14 payload
(`{"event": "prompt_violation", "category", "severity", "message"}`) for every violation at
or above `min_severity`, optionally filtered by `categories`.
`POST /api/actions/test` fires the pipeline manually for hardware bring-up.

## MCP server (agent access to the DB)

`gordon_mcp.py` is a stdio MCP server exposing read-only tools over the hosted API:
`get_dashboard_summary`, `get_daily_summary`, `get_score_history`, `list_events`,
`search_knowledge`, `list_webhooks`, `get_monitoring_status`.

Repo-level `.mcp.json` auto-registers it for Claude Code. Point it at local dev with
`GORDON_API_BASE=http://127.0.0.1:8765`.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/events` | Capture event intake → score → overlay push → actions |
| GET | `/api/events?session_id=&limit=` | Session history |
| POST | `/api/evaluations/{event_id}` | Engine pushes a finished evaluation |
| GET | `/api/dashboard/summary` | All PRD section 13 metrics incl. kitchen rating |
| GET | `/api/dashboard/history?days=7` | Daily score/interruption series |
| GET | `/api/dashboard/daily` | Daily summary text block |
| GET | `/api/knowledge?q=&product=` | Search frontier-knowledge entries |
| POST | `/api/knowledge` | Add an entry manually |
| POST | `/api/knowledge/import/rss` | Import an RSS/Atom feed (e.g. GitHub releases) |
| GET/POST | `/api/webhooks` | List / register device webhooks |
| DELETE | `/api/webhooks/{id}` | Remove a webhook |
| POST | `/api/actions/test` | Fire the action router manually |
| POST | `/api/monitoring/pause` · `/resume` | One-click pause (PRD 22) |
| GET | `/api/monitoring/status` | Paused? |
| DELETE | `/api/history` | Delete all events + evaluations (PRD 22) |
| GET | `/health` | Liveness |

Interactive docs at `http://127.0.0.1:8765/docs` once running.

## Notes

- **Knowledge seed data is demo fixture data** (`seed/knowledge_seed.json`,
  `confidence: "seeded-demo"`). RSS-imported entries are marked `unverified` and always
  carry source + date — Gordon never states a claim without them (PRD section 12).
- "Tokens potentially saved" is an explicit estimate (~4 chars/token on flagged prompts),
  never presented as a measured stat (PRD section 8).
- The mock evaluator's frontier check matches prompts/models against
  `knowledge_updates.previous_option`, so seeding new entries immediately teaches the
  mock engine new outdated-tech detections.
