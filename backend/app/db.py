"""SQLite storage for Gordon's platform service."""
import json
import os
import sqlite3
import threading
from contextlib import contextmanager

DB_PATH = os.environ.get("GORDON_DB", os.path.join(os.path.dirname(__file__), "..", "gordon.db"))

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    event_id      TEXT PRIMARY KEY,
    timestamp     TEXT NOT NULL,
    source        TEXT,
    application   TEXT,
    prompt_text   TEXT,
    selected_model TEXT,
    screenshot_path TEXT,
    session_id    TEXT,
    created_at    TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS evaluations (
    event_id        TEXT PRIMARY KEY REFERENCES events(event_id),
    overall_score   INTEGER NOT NULL,
    primary_category TEXT NOT NULL,
    category_scores TEXT NOT NULL,          -- JSON object
    roast           TEXT,
    diagnosis       TEXT,
    lesson          TEXT,
    improved_prompt TEXT,
    severity        INTEGER DEFAULT 0,
    action          TEXT,
    engine          TEXT DEFAULT 'mock',    -- 'mock' or 'remote'
    created_at      TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS knowledge_updates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product         TEXT NOT NULL,
    what_changed    TEXT NOT NULL,
    release_date    TEXT,
    source          TEXT,
    previous_option TEXT,
    new_option      TEXT,
    why_it_matters  TEXT,
    confidence      TEXT DEFAULT 'seeded-demo',
    imported_from   TEXT DEFAULT 'seed',
    created_at      TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS webhooks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    url          TEXT NOT NULL,
    name         TEXT,
    categories   TEXT DEFAULT '[]',          -- JSON list, empty = all
    min_severity INTEGER DEFAULT 1,
    enabled      INTEGER DEFAULT 1,
    created_at   TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


@contextmanager
def conn():
    with _lock:
        c = sqlite3.connect(DB_PATH)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        finally:
            c.close()


def init_db():
    with conn() as c:
        c.executescript(SCHEMA)
        # migration: structured frontier-source citation on evaluations
        cols = [r["name"] for r in c.execute("PRAGMA table_info(evaluations)")]
        if "source" not in cols:
            c.execute("ALTER TABLE evaluations ADD COLUMN source TEXT")


def get_setting(key: str, default: str | None = None) -> str | None:
    with conn() as c:
        row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    with conn() as c:
        c.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def insert_event(e: dict):
    with conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO events(event_id,timestamp,source,application,"
            "prompt_text,selected_model,screenshot_path,session_id) VALUES(?,?,?,?,?,?,?,?)",
            (e["event_id"], e["timestamp"], e.get("source"), e.get("application"),
             e.get("prompt_text"), e.get("selected_model"), e.get("screenshot_path"),
             e.get("session_id")),
        )


def insert_evaluation(event_id: str, ev: dict, engine: str):
    with conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO evaluations(event_id,overall_score,primary_category,"
            "category_scores,roast,diagnosis,lesson,improved_prompt,severity,action,engine,source) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (event_id, ev["overall_score"], ev["primary_category"],
             json.dumps(ev["category_scores"]), ev.get("roast"), ev.get("diagnosis"),
             ev.get("lesson"), ev.get("improved_prompt"), ev.get("severity", 0),
             ev.get("action"), engine,
             json.dumps(ev["source"]) if ev.get("source") else None),
        )


def rows(query: str, params: tuple = ()) -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute(query, params).fetchall()]


def one(query: str, params: tuple = ()) -> dict | None:
    with conn() as c:
        r = c.execute(query, params).fetchone()
        return dict(r) if r else None


def execute(query: str, params: tuple = ()):
    with conn() as c:
        cur = c.execute(query, params)
        return cur.lastrowid
