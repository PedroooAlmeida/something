"""Incremental roast extraction from a streaming JSON response, plus JSON recovery."""

from __future__ import annotations

import json


class RoastExtractor:
    """Feed streamed text chunks; returns the roast string the moment its closing
    quote arrives, None until then.

    The rubric forces `roast` to be the first key of the JSON object, so the first
    occurrence of `"roast"` followed by a colon is the key. Escaped quotes (\\" and
    \\\\) inside the value are handled by walking the buffer with an escape flag.
    """

    def __init__(self) -> None:
        self._buf = ""
        self._done = False

    @property
    def done(self) -> bool:
        return self._done

    def feed(self, chunk: str) -> str | None:
        if self._done:
            return None
        self._buf += chunk
        return self._try_extract()

    def _try_extract(self) -> str | None:
        buf = self._buf
        key_at = buf.find('"roast"')
        if key_at == -1:
            return None
        i = key_at + len('"roast"')
        # expect optional whitespace, ':', optional whitespace, then the opening quote
        while i < len(buf) and buf[i] in " \t\r\n":
            i += 1
        if i >= len(buf) or buf[i] != ":":
            return None
        i += 1
        while i < len(buf) and buf[i] in " \t\r\n":
            i += 1
        if i >= len(buf) or buf[i] != '"':
            return None
        start = i + 1
        escaped = False
        for j in range(start, len(buf)):
            c = buf[j]
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                self._done = True
                # round-trip through json to resolve \" \\ \n etc.
                return json.loads(buf[start - 1 : j + 1])
        return None  # closing quote not yet streamed


def recover_json(text: str) -> dict:
    """Parse the model's full output into a dict, repairing common damage:
    markdown fences, leading prose, truncated streams (unclosed strings/braces).

    Raises ValueError if nothing object-like can be recovered.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[: -len("```")]
    brace = cleaned.find("{")
    if brace == -1:
        raise ValueError(f"no JSON object in model output: {text[:120]!r}")
    cleaned = cleaned[brace:]

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Truncated stream: close an open string, strip a dangling token, close braces.
    depth = 0
    in_string = False
    escaped = False
    for c in cleaned:
        if escaped:
            escaped = False
        elif c == "\\":
            escaped = True
        elif in_string:
            if c == '"':
                in_string = False
        elif c == '"':
            in_string = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
    repaired = cleaned + ('"' if in_string else "")
    repaired = repaired.rstrip()
    if repaired.endswith((",", ":")):
        repaired = repaired[:-1]
    repaired += "}" * max(depth, 0)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError as exc:
        raise ValueError(f"unrecoverable model output: {text[:200]!r}") from exc
