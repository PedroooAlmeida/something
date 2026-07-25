"""CLI harness: run fixture prompts against the real model, print a score table.

Not pytest — hits the real model, run by hand:
    python -m gordon.harness              # all 23 fixtures, text-only, concurrent
    python -m gordon.harness --smoke      # M1 slice: one prompt end-to-end incl. audio
    python -m gordon.harness --prewarm    # cache demo audio for the fixture roasts
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
import uuid

from gordon import config, engine, voice
from gordon.schemas import CaptureEvent, EngineResponse

SMOKE_PROMPT = "Make this work."


def _load_fixtures() -> list[dict]:
    return json.loads(config.FIXTURES_PATH.read_text())


def _event(prompt_text: str, event_id: str, personality_id: str = "angry_chef") -> CaptureEvent:
    return CaptureEvent(
        event_id=event_id,
        source="harness",
        application="harness",
        prompt_text=prompt_text,
        session_id=f"harness-{uuid.uuid4().hex[:8]}",
        personality_id=personality_id,
    )


async def _run_one(
    fixture: dict, sem: asyncio.Semaphore, with_audio: bool = False
) -> tuple[dict, EngineResponse | Exception]:
    async with sem:
        try:
            response = await engine.evaluate(
                _event(fixture["prompt_text"], fixture["id"]), with_audio=with_audio
            )
            return fixture, response
        except Exception as exc:  # noqa: BLE001 — a failed fixture is a table row, not a crash
            return fixture, exc


async def run_all(with_audio: bool = False) -> None:
    fixtures = _load_fixtures()
    sem = asyncio.Semaphore(config.HARNESS_CONCURRENCY)
    t0 = time.perf_counter()
    results = await asyncio.gather(*(_run_one(f, sem, with_audio) for f in fixtures))
    wall = time.perf_counter() - t0

    print()
    print(f"{'id':<11} {'expected':<20} {'got':<20} {'score':>5} {'int':<5} {'words':>5}  roast")
    print("-" * 120)
    cat_hits = cat_total = 0
    good_hits = good_total = 0
    over_budget = 0
    failures = 0
    for fixture, result in results:
        if isinstance(result, Exception):
            failures += 1
            print(f"{fixture['id']:<11} {'ERROR':<20} {type(result).__name__}: {result}")
            continue
        words = len(result.roast.split())
        if words > config.MAX_ROAST_WORDS:
            over_budget += 1
        if fixture["good"]:
            good_total += 1
            ok = result.overall_score >= config.GOOD_PROMPT_MIN_SCORE and not result.should_interrupt
            good_hits += ok
            expected = "(good)"
            mark = "PASS" if ok else "FAIL"
        else:
            cat_total += 1
            ok = result.primary_category == fixture["expected_category"]
            cat_hits += ok
            expected = fixture["expected_category"]
            mark = "PASS" if ok else "FAIL"
        print(
            f"{fixture['id']:<11} {expected:<20} {result.primary_category:<20} "
            f"{result.overall_score:>5} {str(result.should_interrupt):<5} {words:>5}  "
            f"[{mark}] {result.roast}"
        )

    print("-" * 120)
    print(
        f"category accuracy {cat_hits}/{cat_total} | good prompts {good_hits}/{good_total} "
        f"(>= {config.GOOD_PROMPT_MIN_SCORE}, no interrupt) | roasts over "
        f"{config.MAX_ROAST_WORDS}w: {over_budget} | errors: {failures} | wall {wall:.1f}s"
    )


async def run_smoke() -> None:
    """M1 acceptance: one hardcoded prompt end-to-end, audio included."""
    response = await engine.evaluate(_event(SMOKE_PROMPT, "smoke-1"), with_audio=True)
    print(json.dumps(response.model_dump(), indent=2))
    if response.audio_cache_key:
        path = await voice.wait_for_audio(response.audio_cache_key)
        print(f"\naudio: {path if path else 'NOT READY / FAILED'}")
        if path:
            print(f"play it:  afplay {path}")
    else:
        print("\naudio: unavailable")


async def run_prewarm() -> None:
    """Synthesize demo audio ahead of time: fixture roasts + the safe fallback line."""
    fixtures = _load_fixtures()
    sem = asyncio.Semaphore(config.HARNESS_CONCURRENCY)
    results = await asyncio.gather(*(_run_one(f, sem, with_audio=True) for f in fixtures))
    keys = [r.audio_cache_key for _, r in results if isinstance(r, EngineResponse) and r.audio_cache_key]
    # wait for every synthesis task to land on disk
    paths = await asyncio.gather(*(voice.wait_for_audio(k) for k in keys))
    from gordon import personalities  # local import: harness-only dependency direction

    for p in personalities.all_ids():
        persona = personalities.get(p)
        await voice.prewarm(
            [(config.SAFE_FALLBACK_ROAST, persona.voice_id, persona.voice_settings(2))]
        )
    done = sum(1 for p in paths if p)
    print(f"prewarmed {done}/{len(keys)} fixture roasts + fallback lines into {config.AUDIO_CACHE_DIR}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Gordon harness")
    parser.add_argument("--smoke", action="store_true", help="single end-to-end prompt incl. audio")
    parser.add_argument("--prewarm", action="store_true", help="cache demo audio")
    args = parser.parse_args()
    if args.smoke:
        asyncio.run(run_smoke())
    elif args.prewarm:
        asyncio.run(run_prewarm())
    else:
        asyncio.run(run_all())


if __name__ == "__main__":
    main()
