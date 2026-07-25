"""Orchestration — evaluate(). No prompt text, no HTTP calls, no regexes here."""

from __future__ import annotations

import time

from pydantic import ValidationError

from gordon import config, knowledge, llm, parsing, personalities, rubric, safety, voice
from gordon.personalities import Personality
from gordon.schemas import CaptureEvent, EngineResponse, Evaluation, TimingMs


async def evaluate(event: CaptureEvent) -> EngineResponse:
    """Stream the evaluation model; the roast is spoken the moment its closing
    quote arrives (invariant 1), audio never blocks the response (invariant 2),
    safety always runs before synthesis (invariant 3)."""
    t0 = time.perf_counter()
    personality = personalities.get(event.personality_id)
    records = knowledge.match(event.prompt_text)
    prompt = rubric.build_prompt(event, personality.style_note, records)
    safety_context = rubric.context_for_safety(event, records)

    evaluation: Evaluation | None = None
    spoken_roast: str | None = None
    roast_ready_ms: int | None = None
    handle: voice.SynthHandle | None = None
    last_error: Exception | None = None

    for attempt in range(config.LLM_ATTEMPTS):
        raw: list[str] = []
        extractor = parsing.RoastExtractor()
        try:
            async for chunk in llm.stream_llm(prompt):
                raw.append(chunk)
                if spoken_roast is None:
                    candidate = extractor.feed(chunk)
                    if candidate is not None:
                        roast_ready_ms = _ms_since(t0)
                        spoken_roast, handle = _speak(candidate, safety_context, personality)
            evaluation = Evaluation.model_validate(parsing.recover_json("".join(raw)))
            break
        except (ValueError, ValidationError, llm.LLMError) as exc:
            last_error = exc
            print(f"[engine] attempt {attempt + 1}/{config.LLM_ATTEMPTS} unparseable: {exc}")

    if evaluation is None:
        raise RuntimeError(f"evaluation failed after {config.LLM_ATTEMPTS} attempts") from last_error

    # Extractor missed (unexpected key order etc.) — speak the validated roast now.
    if spoken_roast is None:
        roast_ready_ms = _ms_since(t0)
        spoken_roast, handle = _speak(evaluation.roast, safety_context, personality)

    response = _respond(event, personality, evaluation, spoken_roast, handle, roast_ready_ms, t0)
    print(
        f"[engine] event={event.event_id} personality={personality.id} "
        f"score={response.overall_score} roast_ready={response.timing_ms.roast_ready}ms "
        f"total={response.timing_ms.total}ms audio={response.audio_status}"
    )
    return response


def _speak(
    roast: str, safety_context: str, personality: Personality
) -> tuple[str, voice.SynthHandle | None]:
    """Safety filter, then fire synthesis in the background. Never blocks.
    Returns the text that is both shown and spoken (identical by design)."""
    safe, dropped = safety.filter_text(roast, safety_context)
    for note in dropped:
        print(f"[safety] dropped from roast: {note}")
    safe = safe.strip()
    if not safe:
        return config.SAFE_FALLBACK_ROAST, None
    settings = personality.voice_settings(config.SYNTH_DEFAULT_SEVERITY)
    return safe, voice.start_synthesis(safe, personality.voice_id, settings)


def _respond(
    event: CaptureEvent,
    personality: Personality,
    evaluation: Evaluation,
    spoken_roast: str,
    handle: voice.SynthHandle | None,
    roast_ready_ms: int | None,
    t0: float,
) -> EngineResponse:
    total_ms = _ms_since(t0)
    action = config.ACTION_BY_SEVERITY.get(evaluation.severity, "desk_buzzer")
    return EngineResponse(
        roast=spoken_roast,
        overall_score=evaluation.overall_score,
        primary_category=evaluation.primary_category,
        category_scores=evaluation.category_scores,
        diagnosis=evaluation.diagnosis,
        lesson=evaluation.lesson,
        improved_prompt=evaluation.improved_prompt,
        severity=evaluation.severity,
        should_interrupt=evaluation.should_interrupt,
        personality_id=personality.id,
        voice_id=personality.voice_id,
        audio_url=f"/audio/{handle.key}" if handle else "",
        audio_cache_key=handle.key if handle else "",
        audio_status=handle.status if handle else "unavailable",
        action=action if evaluation.should_interrupt else "none",
        timing_ms=TimingMs(
            roast_ready=roast_ready_ms if roast_ready_ms is not None else total_ms,
            total=total_ms,
        ),
    )


def _ms_since(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)
