"""Seeded frontier-knowledge records + keyword match (M6).

For now: loader + match API in place, records arrive in M6.

# IMPORTER STUB: a real importer would pull release feeds (RSS/changelogs) and
# append validated records to data/releases.json. Out of scope for the hackathon —
# records are hand-seeded. If M6 gets cut, Person 4 takes this file.
"""

from __future__ import annotations

import json
from functools import lru_cache

from gordon import config


_REQUIRED_FIELDS = frozenset(
    {"technology", "what_changed", "release_date", "source_url", "old_option", "new_option"}
)


@lru_cache(maxsize=1)
def _records() -> list[dict]:
    if not config.RELEASES_PATH.exists():
        return []
    try:
        raw = json.loads(config.RELEASES_PATH.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[knowledge] failed to load {config.RELEASES_PATH}: {exc}")
        return []
    records = [
        r for r in raw
        if isinstance(r, dict) and _REQUIRED_FIELDS <= set(r)
    ] if isinstance(raw, list) else []
    if len(records) != (len(raw) if isinstance(raw, list) else 0):
        print(f"[knowledge] skipped malformed entries in {config.RELEASES_PATH}")
    return records


def match(prompt_text: str) -> list[dict]:
    """Keyword match: a record is relevant if any of its keywords appear in the
    prompt (case-insensitive). Returns at most KNOWLEDGE_MAX_MATCHES records."""
    lowered = prompt_text.lower()
    hits: list[dict] = []
    for record in _records():
        keywords = record.get("keywords") or [record.get("technology", "")]
        if any(k.lower() in lowered for k in keywords if k):
            hits.append(record)
        if len(hits) >= config.KNOWLEDGE_MAX_MATCHES:
            break
    return hits
