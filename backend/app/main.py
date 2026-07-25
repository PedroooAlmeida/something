"""Gordon platform service — Person 4.

Run:  uvicorn app.main:app --port 8765 --reload   (from backend/)

Integration points:
  Person 2 (capture)  -> POST /api/events                (shared format, PRD 17)
  Person 3 (engine)   -> set GORDON_ENGINE_URL, or POST /api/evaluations/{event_id}
  Person 1 (overlay)  -> WS  /ws/overlay + GET /api/dashboard/*
  Devices             -> POST /api/webhooks to subscribe to violations
"""
import asyncio
import json

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

import base64
import os
import re as _re
from pathlib import Path

from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import actions, db, evaluator, knowledge, progress
from .models import (CaptureEvent, Evaluation, KnowledgeUpdate,
                     RssImportRequest, ScreenshotUpload, WebhookRegistration,
                     WebhookUpdate)
from .redaction import redact

SCREENSHOT_DIR = os.environ.get(
    "GORDON_SCREENSHOTS",
    os.path.join(os.path.dirname(db.DB_PATH), "screenshots"),
)

app = FastAPI(title="Gordon Platform Service", version="0.1.0")

# Overlay (tauri/electron), extension content scripts, and local dashboards all
# talk to us from different origins on localhost — open CORS is fine for a
# local-only hackathon service.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ---------------------------------------------------------------- overlay WS --
class OverlayHub:
    def __init__(self):
        self.clients: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.clients.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.clients:
            self.clients.remove(ws)

    async def broadcast(self, message: dict):
        dead = []
        for ws in self.clients:
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


hub = OverlayHub()


@app.websocket("/ws/overlay")
async def overlay_ws(ws: WebSocket):
    await hub.connect(ws)
    try:
        while True:
            await ws.receive_text()  # overlay may send pings; we just keep the socket open
    except WebSocketDisconnect:
        hub.disconnect(ws)


# ------------------------------------------------------------------- startup --
@app.on_event("startup")
def startup():
    db.init_db()
    seeded = knowledge.seed_if_empty()
    if seeded:
        print(f"[startup] seeded {seeded} frontier-knowledge entries")


@app.get("/health")
def health():
    return {"ok": True, "service": "gordon-platform", "version": "0.1.0"}


# ---------------------------------------------------------------- monitoring --
@app.get("/api/monitoring/status")
def monitoring_status():
    return {"paused": db.get_setting("paused", "0") == "1"}


@app.post("/api/monitoring/pause")
async def monitoring_pause():
    db.set_setting("paused", "1")
    await hub.broadcast({"type": "monitoring", "paused": True})
    return {"paused": True}


@app.post("/api/monitoring/resume")
async def monitoring_resume():
    db.set_setting("paused", "0")
    await hub.broadcast({"type": "monitoring", "paused": False})
    return {"paused": False}


# -------------------------------------------------------------- personality --
@app.get("/api/settings/personality")
def personality_get():
    return {"personality_id": db.get_setting("personality_id", "angry_chef")}


@app.put("/api/settings/personality")
async def personality_set(body: dict):
    pid = (body.get("personality_id") or "").strip()
    if not pid:
        raise HTTPException(422, "personality_id required")
    db.set_setting("personality_id", pid)
    await hub.broadcast({"type": "personality", "personality_id": pid})
    return {"personality_id": pid}


# -------------------------------------------------------------- event intake --
def _normalize(evaluation: dict) -> dict:
    """Person 3's engine never emits severity 0 — 'leave the user alone' is
    should_interrupt=False. Normalize so severity 0 == no violation everywhere
    downstream (actions, interruption counts)."""
    if evaluation.get("should_interrupt") is False:
        evaluation["severity"] = 0
        evaluation["action"] = "none"
    return evaluation


async def _process(event: dict) -> dict:
    """Score -> store -> push to overlay -> fire actions. Returns the evaluation."""
    evaluation, engine = await asyncio.to_thread(evaluator.evaluate, event)
    evaluation = _normalize(evaluation)
    db.insert_evaluation(event["event_id"], evaluation, engine)

    await hub.broadcast({"type": "coaching_response", "event": event, "evaluation": evaluation})

    if evaluation.get("severity", 0) >= 1:
        message = evaluation.get("diagnosis") or evaluation.get("roast") or "prompt violation"
        await asyncio.to_thread(
            actions.dispatch, evaluation["primary_category"], evaluation["severity"], message
        )
    return evaluation


@app.post("/api/events")
async def receive_event(event: CaptureEvent):
    """Main pipeline entry: Person 2 posts a capture event here."""
    if db.get_setting("paused", "0") == "1":
        return {"status": "paused", "evaluated": False}

    data = event.model_dump()
    data["prompt_text"], redactions = redact(data["prompt_text"])
    # capture services that don't know the selected personality inherit the
    # overlay's persisted choice
    if data.get("personality_id") in (None, "", "angry_chef"):
        data["personality_id"] = db.get_setting("personality_id", "angry_chef")
    db.insert_event(data)

    evaluation = await _process(data)
    return {"status": "ok", "evaluated": True, "redactions": redactions,
            "evaluation": evaluation}


@app.post("/api/evaluations/{event_id}")
async def receive_evaluation(event_id: str, evaluation: Evaluation):
    """Alternative integration path: Person 3's engine pushes a finished
    evaluation for an already-stored event (instead of us pulling)."""
    event = db.one("SELECT * FROM events WHERE event_id=?", (event_id,))
    if not event:
        raise HTTPException(404, "unknown event_id — POST /api/events first")
    ev = _normalize(evaluation.model_dump())
    db.insert_evaluation(event_id, ev, "remote-push")
    await hub.broadcast({"type": "coaching_response", "event": event, "evaluation": ev})
    if ev["severity"] >= 1:
        await asyncio.to_thread(actions.dispatch, ev["primary_category"], ev["severity"],
                                ev.get("diagnosis") or ev.get("roast") or "prompt violation")
    return {"status": "ok"}


@app.get("/api/events")
def list_events(session_id: str | None = None, limit: int = 50):
    query = ("SELECT e.*, ev.overall_score, ev.primary_category, ev.severity, ev.roast "
             "FROM events e LEFT JOIN evaluations ev USING(event_id)")
    params: tuple = ()
    if session_id:
        query += " WHERE e.session_id=?"
        params = (session_id,)
    query += " ORDER BY e.created_at DESC LIMIT ?"
    return db.rows(query, params + (min(limit, 500),))


# ----------------------------------------------------------------- dashboard --
@app.get("/api/dashboard/summary")
def dashboard_summary():
    return progress.summary()


@app.get("/api/dashboard/history")
def dashboard_history(days: int = 7):
    return progress.history(days)


@app.get("/api/dashboard/daily")
def dashboard_daily():
    return progress.daily_summary()


# ----------------------------------------------------------------- knowledge --
@app.get("/api/knowledge")
def knowledge_list(q: str | None = None, product: str | None = None):
    return knowledge.search(q, product)


@app.post("/api/knowledge")
def knowledge_add(update: KnowledgeUpdate):
    new_id = db.execute(
        "INSERT INTO knowledge_updates(product, what_changed, release_date, source, "
        "previous_option, new_option, why_it_matters, confidence, imported_from) "
        "VALUES(?,?,?,?,?,?,?,?, 'manual')",
        (update.product, update.what_changed, update.release_date, update.source,
         update.previous_option, update.new_option, update.why_it_matters, update.confidence),
    )
    return {"id": new_id}


@app.post("/api/knowledge/import/rss")
async def knowledge_import(reqbody: RssImportRequest):
    try:
        return await asyncio.to_thread(knowledge.import_feed, reqbody.url,
                                       reqbody.product, reqbody.limit)
    except Exception as exc:
        raise HTTPException(422, f"feed import failed: {exc}")


# ------------------------------------------------------------------ webhooks --
@app.get("/api/webhooks")
def webhooks_list():
    hooks = db.rows("SELECT * FROM webhooks ORDER BY id")
    for h in hooks:
        h["categories"] = json.loads(h["categories"] or "[]")
        h["enabled"] = bool(h["enabled"])
    return hooks


@app.post("/api/webhooks")
def webhooks_add(reg: WebhookRegistration):
    new_id = db.execute(
        "INSERT INTO webhooks(url, name, categories, min_severity) VALUES(?,?,?,?)",
        (reg.url, reg.name, json.dumps(reg.categories), reg.min_severity),
    )
    return {"id": new_id}


@app.patch("/api/webhooks/{hook_id}")
def webhooks_update(hook_id: int, upd: WebhookUpdate):
    hook = db.one("SELECT * FROM webhooks WHERE id=?", (hook_id,))
    if not hook:
        raise HTTPException(404, "unknown webhook id")
    fields = {
        "enabled": int(upd.enabled) if upd.enabled is not None else None,
        "min_severity": upd.min_severity,
        "categories": json.dumps(upd.categories) if upd.categories is not None else None,
        "name": upd.name,
        "url": upd.url,
    }
    sets = {k: v for k, v in fields.items() if v is not None}
    if sets:
        db.execute(f"UPDATE webhooks SET {', '.join(f'{k}=?' for k in sets)} WHERE id=?",
                   (*sets.values(), hook_id))
    return {"updated": hook_id, "fields": list(sets)}


@app.delete("/api/webhooks/{hook_id}")
def webhooks_delete(hook_id: int):
    db.execute("DELETE FROM webhooks WHERE id=?", (hook_id,))
    return {"deleted": hook_id}


@app.post("/api/actions/test")
async def actions_test(category: str = "token_conservation", severity: int = 2,
                       message: str = "Test firing from /api/actions/test"):
    """Fire the action pipeline without a real prompt — for wiring up the buzzer."""
    await asyncio.to_thread(actions.dispatch, category, severity, message)
    await hub.broadcast({"type": "action_test",
                         "category": category, "severity": severity, "message": message})
    return {"fired": True}


# --------------------------------------------------------------- screenshots --
@app.post("/api/screenshots")
def screenshot_upload(up: ScreenshotUpload):
    """Cross-machine screenshot handoff for Person 2. PRD 22: not persisted by
    default — kept only until the event is evaluated or history is deleted."""
    if not _re.fullmatch(r"[\w-]+", up.event_id):
        raise HTTPException(422, "bad event_id")
    try:
        blob = base64.b64decode(up.image_base64, validate=True)
    except Exception:
        raise HTTPException(422, "image_base64 is not valid base64")
    if len(blob) > 8_000_000:
        raise HTTPException(413, "screenshot too large (8MB max)")
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    path = os.path.join(SCREENSHOT_DIR, f"{up.event_id}.png")
    with open(path, "wb") as f:
        f.write(blob)
    return {"screenshot_path": f"/api/screenshots/{up.event_id}"}


@app.get("/api/screenshots/{event_id}")
def screenshot_get(event_id: str):
    if not _re.fullmatch(r"[\w-]+", event_id):
        raise HTTPException(422, "bad event_id")
    path = os.path.join(SCREENSHOT_DIR, f"{event_id}.png")
    if not os.path.exists(path):
        raise HTTPException(404, "no screenshot for this event")
    from fastapi.responses import FileResponse
    return FileResponse(path, media_type="image/png")


# -------------------------------------------------------------------- privacy --
@app.delete("/api/history")
def delete_history():
    """One-click 'delete my history' (PRD 22). Keeps knowledge + webhooks.
    Also removes any stored screenshots."""
    with db.conn() as c:
        events = c.execute("DELETE FROM events").rowcount
        evals = c.execute("DELETE FROM evaluations").rowcount
    shots = 0
    if os.path.isdir(SCREENSHOT_DIR):
        for name in os.listdir(SCREENSHOT_DIR):
            os.remove(os.path.join(SCREENSHOT_DIR, name))
            shots += 1
    return {"deleted_events": events, "deleted_evaluations": evals,
            "deleted_screenshots": shots}


# ------------------------------------------------------------- static site --
# Serve the landing page + browser demo same-origin so /api and audio work
# from a plain `./start.sh` with no separate web server. Only allowlisted
# paths — NEVER mount the repo root (it contains .env).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SITE_FILES = {"index.html", "fonts.css", "gordon-favicon.svg"}

for _d in ("design_handoff_gordon_overlay", "logo"):
    _p = _REPO_ROOT / _d
    if _p.is_dir():
        app.mount(f"/site/{_d}", StaticFiles(directory=_p, html=True), name=_d)


@app.get("/", include_in_schema=False)
def _root():
    return RedirectResponse("/site/index.html")


@app.get("/site/{name}", include_in_schema=False)
def _site_file(name: str):
    if name not in _SITE_FILES:
        raise HTTPException(status_code=404)
    return FileResponse(_REPO_ROOT / name)
