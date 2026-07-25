"""Smoke suite for the platform service — the integration seams the other three
people depend on. Run: .venv/bin/pytest tests/ -q"""
import base64
import uuid


def _event(prompt: str, **kw) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": "2026-07-25T12:00:00Z",
        "prompt_text": prompt,
        "session_id": "test",
        **kw,
    }


def test_health(client):
    assert client.get("/health").json()["ok"] is True


def test_bad_prompt_scores_low_and_counts(client):
    r = client.post("/api/events", json=_event("Build me an app.")).json()
    ev = r["evaluation"]
    assert r["evaluated"] and ev["overall_score"] < 45
    assert ev["primary_category"] == "prompt_specificity"
    assert ev["severity"] >= 2 and ev["action"] in ("desk_buzzer", "bell_bot")
    assert ev["should_interrupt"] is True
    assert client.get("/api/dashboard/summary").json()["total_interruptions"] == 1


def test_good_prompt_does_not_interrupt(client):
    r = client.post("/api/events", json=_event(
        "In auth.ts, login() returns a 401 after token expiry. Expected: refresh "
        "and retry once. I already tried bumping expiry. Fix the refresh logic "
        "without changing the API and write a test that reproduces it.")).json()
    ev = r["evaluation"]
    assert ev["severity"] == 0 and ev["action"] == "none" and ev["should_interrupt"] is False
    assert client.get("/api/dashboard/summary").json()["total_interruptions"] == 0


def test_frontier_hit_carries_source(client):
    r = client.post("/api/events", json=_event(
        "Write a date picker with moment.js please", selected_model="claude-3-opus")).json()
    ev = r["evaluation"]
    assert ev["primary_category"] == "frontier_awareness"
    src = ev["source"]
    assert src and src["url"] and src["date"]  # overlay never renders a claim without both


def test_engine_push_normalizes_should_interrupt(client):
    e = _event("whatever")
    client.post("/api/events", json=e)
    client.delete("/api/history")
    client.post("/api/events", json=e)
    scores = {c: 80 for c in ("prompt_specificity", "token_conservation",
                              "frontier_awareness", "tool_selection",
                              "context_management", "verification")}
    r = client.post(f"/api/evaluations/{e['event_id']}", json={
        "overall_score": 85, "primary_category": "verification",
        "category_scores": scores, "roast": "ok", "diagnosis": "d", "lesson": "l",
        "improved_prompt": "p", "severity": 2, "should_interrupt": False,
        "audio_url": "/audio/abc", "voice_id": "ember"})
    assert r.status_code == 200


def test_paused_gate(client):
    client.post("/api/monitoring/pause")
    r = client.post("/api/events", json=_event("Build me an app.")).json()
    assert r == {"status": "paused", "evaluated": False}
    client.post("/api/monitoring/resume")


def test_redaction_before_storage(client):
    client.post("/api/events", json=_event(
        "fix it, key sk-abc123def456ghi789jkl012 mail bob@example.com"))
    stored = client.get("/api/events", params={"limit": 1}).json()[0]["prompt_text"]
    assert "sk-abc123" not in stored and "bob@example.com" not in stored
    assert "[redacted: api_key]" in stored and "[redacted: pii]" in stored


def test_webhook_crud_and_patch(client):
    hid = client.post("/api/webhooks", json={"url": "http://x/y", "name": "t"}).json()["id"]
    client.patch(f"/api/webhooks/{hid}", json={"enabled": False, "min_severity": 3})
    hook = [h for h in client.get("/api/webhooks").json() if h["id"] == hid][0]
    assert hook["enabled"] is False and hook["min_severity"] == 3
    assert client.delete(f"/api/webhooks/{hid}").status_code == 200


def test_personality_setting_flows_into_events(client):
    client.put("/api/settings/personality", json={"personality_id": "prof"})
    assert client.get("/api/settings/personality").json()["personality_id"] == "prof"
    r = client.post("/api/events", json=_event("Build me an app.")).json()
    assert r["evaluation"]["personality_id"] == "prof"
    client.put("/api/settings/personality", json={"personality_id": "angry_chef"})


def test_screenshot_roundtrip_and_wipe(client):
    b64 = base64.b64encode(b"\x89PNG fake").decode()
    r = client.post("/api/screenshots", json={"event_id": "shot-t1", "image_base64": b64})
    assert r.status_code == 200
    assert client.get("/api/screenshots/shot-t1").status_code == 200
    wiped = client.delete("/api/history").json()
    assert wiped["deleted_screenshots"] >= 1
    assert client.get("/api/screenshots/shot-t1").status_code == 404


def test_dashboard_summary_shape(client):
    client.post("/api/events", json=_event("Build me an app."))
    s = client.get("/api/dashboard/summary").json()
    for key in ("total_interruptions", "interruptions_today", "interruptions_yesterday",
                "average_prompt_score", "tokens_potentially_saved_estimate",
                "kitchen_rating", "category_averages", "category_hits_14d",
                "worst_category_by_hits"):
        assert key in s
    assert s["kitchen_rating"]["label"] in (
        "Dishwasher", "Commis", "Line Cook", "Chef de Partie", "Head Chef")


def test_knowledge_seeded_and_searchable(client):
    assert len(client.get("/api/knowledge").json()) >= 5
    hits = client.get("/api/knowledge", params={"q": "moment"}).json()
    assert hits and all(h["source"] for h in hits)
