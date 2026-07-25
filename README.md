# Gordon — AI Coding Coach

A desktop overlay that watches how you use AI coding tools, scores every prompt,
roasts you (angry-chef style), teaches you the fix, and triggers a desk buzzer when
you deserve it.

## Repo layout / team split

| Folder | Owner | What lives here |
|---|---|---|
| `overlay/` | Person 1 | Always-on-top desktop overlay, character, roast cards, audio playback, dashboard UI (Tauri/Electron + React) |
| `extension/` | Person 2 | Chrome extension: prompt-submission detection, prompt/model extraction, screenshot trigger, event delivery |
| `engine/` | Person 3 | AI evaluation + coaching: rubric, roasts, prompt rewriting, personalities, ElevenLabs voice |
| `backend/` | Person 4 | Platform service: event API, SQLite, dashboard analytics, knowledge service, webhook action router — **built, see `backend/README.md`** |

## The contract (agree-first, per PRD section 19)

- Shared event JSON: PRD section 17, implemented verbatim in `backend/app/models.py`.
- **Hosted platform service: `https://gordon-platform.fly.dev`** (docs at `/docs`).
  Local dev alternative: `http://127.0.0.1:8765`.
- Overlay receives coaching responses over `wss://gordon-platform.fly.dev/ws/overlay`.
- Devices subscribe via `POST /api/webhooks` and receive the section 14 violation payload.
- The backend ships a mock evaluator, so every other component can integrate today
  without waiting for the engine.

## Quickstart (backend + full pipeline demo)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8765 --reload
# second terminal:
python scripts/send_mock_events.py
```
