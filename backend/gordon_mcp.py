"""Gordon MCP server — read-only access to Gordon's data for AI agents.

Wraps the platform REST API (works against hosted Fly or local dev), so it
never needs direct filesystem access to the SQLite volume.

Run (stdio):  python gordon_mcp.py
Point at local dev:  GORDON_API_BASE=http://127.0.0.1:8765 python gordon_mcp.py
"""
import json
import os
import urllib.parse
import urllib.request

from mcp.server.fastmcp import FastMCP

API_BASE = os.environ.get("GORDON_API_BASE", "https://gordon-platform.fly.dev")

mcp = FastMCP("gordon")


def _get(path: str, params: dict | None = None) -> str:
    if params:
        clean = {k: v for k, v in params.items() if v is not None}
        if clean:
            path += "?" + urllib.parse.urlencode(clean)
    with urllib.request.urlopen(API_BASE + path, timeout=15) as resp:
        return json.dumps(json.loads(resp.read().decode()), indent=2)


@mcp.tool()
def get_dashboard_summary() -> str:
    """All progress metrics: interruption counts, average prompt score, tokens
    potentially saved (estimate), best/worst/most-common mistake categories,
    per-category averages, and the current kitchen rating."""
    return _get("/api/dashboard/summary")


@mcp.tool()
def get_daily_summary() -> str:
    """Today's 'you were yelled at N times' summary with per-category breakdown
    and yesterday comparison."""
    return _get("/api/dashboard/daily")


@mcp.tool()
def get_score_history(days: int = 7) -> str:
    """Daily series of prompt counts, interruptions, and average score for the
    last N days — the improvement-over-time chart data."""
    return _get("/api/dashboard/history", {"days": days})


@mcp.tool()
def list_events(session_id: str | None = None, limit: int = 20) -> str:
    """Recent captured prompts joined with their evaluations (score, primary
    category, severity, roast). Optionally filter by session_id."""
    return _get("/api/events", {"session_id": session_id, "limit": limit})


@mcp.tool()
def search_knowledge(query: str | None = None, product: str | None = None) -> str:
    """Search the frontier-knowledge database (model/library/tool updates with
    release date, source, previous vs new option, and confidence level)."""
    return _get("/api/knowledge", {"q": query, "product": product})


@mcp.tool()
def list_webhooks() -> str:
    """Registered punishment-device webhooks with their category filters and
    severity thresholds."""
    return _get("/api/webhooks")


@mcp.tool()
def get_monitoring_status() -> str:
    """Whether Gordon's monitoring is currently paused."""
    return _get("/api/monitoring/status")


if __name__ == "__main__":
    mcp.run()
