"""Keyword matcher + seeded releases.json integrity."""

from __future__ import annotations

import json

from gordon import config, knowledge

REQUIRED_FIELDS = {
    "technology", "what_changed", "release_date", "source_url", "old_option", "new_option",
}


def setup_function() -> None:
    knowledge._records.cache_clear()


def test_releases_file_shape() -> None:
    records = json.loads(config.RELEASES_PATH.read_text())
    assert len(records) == 10
    for record in records:
        assert REQUIRED_FIELDS <= set(record), record.get("technology")
        assert record["keywords"], "keywords drive the matcher"
        assert record["source_url"].startswith("https://")
        # release_date is YYYY-MM-DD
        y, m, d = record["release_date"].split("-")
        assert len(y) == 4 and len(m) == 2 and len(d) == 2


def test_match_outdated_react_prompt() -> None:
    hits = knowledge.match("Write me a React class component using componentWillMount to fetch data")
    assert any(r["technology"] == "React 19" for r in hits)


def test_match_outdated_python_setup_prompt() -> None:
    hits = knowledge.match("Set up my project with setup.py, requirements.txt and a virtualenv")
    assert any("uv" in r["technology"] for r in hits)


def test_match_is_case_insensitive() -> None:
    assert knowledge.match("scaffold with CREATE-REACT-APP please")


def test_no_match_returns_empty() -> None:
    assert knowledge.match("Fix the off-by-one in my binary search") == []


def test_match_caps_at_configured_max() -> None:
    everything = "componentWillMount create-react-app requirements.txt tailwind.config.js .eslintrc gpt-4o"
    assert len(knowledge.match(everything)) <= config.KNOWLEDGE_MAX_MATCHES
