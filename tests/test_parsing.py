"""Roast extractor + JSON recovery. Spec-required cases: None on partial stream,
correct string once the closing quote arrives, escaped quotes handled."""

from __future__ import annotations

import json

from gordon.parsing import RoastExtractor, recover_json


def test_partial_stream_returns_none() -> None:
    ex = RoastExtractor()
    assert ex.feed('{"roast": "This prompt is r') is None
    assert ex.feed("aw in the midd") is None
    assert not ex.done


def test_returns_roast_at_closing_quote() -> None:
    ex = RoastExtractor()
    assert ex.feed('{"roast": "Raw. Send it back') is None
    assert ex.feed('.", "overall_score": 12') == "Raw. Send it back."
    assert ex.done


def test_escaped_quotes_inside_roast() -> None:
    ex = RoastExtractor()
    chunk = '{"roast": "You typed \\"make this work\\" and prayed'
    assert ex.feed(chunk) is None
    got = ex.feed('.", "overall_score": 5}')
    assert got == 'You typed "make this work" and prayed.'


def test_escaped_backslash_before_quote() -> None:
    ex = RoastExtractor()
    got = ex.feed('{"roast": "path C:\\\\", "overall_score": 1}')
    assert got == "path C:\\"


def test_key_split_across_chunks() -> None:
    ex = RoastExtractor()
    for chunk in ['{"ro', 'ast"', " : ", '"Bl', "and."]:
        assert ex.feed(chunk) is None
    assert ex.feed('"') == "Bland."


def test_feed_after_done_returns_none() -> None:
    ex = RoastExtractor()
    assert ex.feed('{"roast": "x", ') == "x"
    assert ex.feed('"overall_score": 3}') is None


def test_recover_clean_json() -> None:
    payload = {"roast": "x", "overall_score": 10}
    assert recover_json(json.dumps(payload)) == payload


def test_recover_fenced_json() -> None:
    assert recover_json('```json\n{"roast": "x"}\n```') == {"roast": "x"}


def test_recover_truncated_stream() -> None:
    got = recover_json('{"roast": "cut off here", "category_scores": {"a": 1')
    assert got["roast"] == "cut off here"
    assert got["category_scores"] == {"a": 1}


def test_recover_truncated_mid_string() -> None:
    got = recover_json('{"roast": "half a sent')
    assert got["roast"] == "half a sent"


def test_recover_garbage_raises() -> None:
    import pytest

    with pytest.raises(ValueError):
        recover_json("the model said nothing useful")
