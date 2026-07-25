"""stream_llm() — THE ONLY place a provider SDK is imported.

Provider: Anthropic (Claude). Swap providers by rewriting this one function;
nothing else imports the SDK. Callers hand over a provider-neutral PromptBundle
(built in rubric.py) and receive raw text deltas.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import anthropic

from gordon import config
from gordon.rubric import PromptBundle

_client: anthropic.AsyncAnthropic | None = None


class LLMError(RuntimeError):
    """Provider failure, normalized so callers never import SDK exception types."""


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        # No key in env/.env -> zero-arg client so the SDK can resolve an
        # `ant auth login` profile or ANTHROPIC_AUTH_TOKEN instead.
        kwargs: dict = {"timeout": config.EVAL_TIMEOUT_S}
        if config.ANTHROPIC_API_KEY:
            kwargs["api_key"] = config.ANTHROPIC_API_KEY
        _client = anthropic.AsyncAnthropic(**kwargs)
    return _client


def _user_content(prompt: PromptBundle) -> list[dict] | str:
    if prompt.image_b64:
        return [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": prompt.image_media_type,
                    "data": prompt.image_b64,
                },
            },
            {"type": "text", "text": prompt.user_text},
        ]
    return prompt.user_text


async def stream_llm(
    prompt: PromptBundle,
    *,
    model: str | None = None,
    max_tokens: int | None = None,
) -> AsyncIterator[str]:
    """Stream raw text deltas from the evaluation model.

    Latency setup for invariant 1 (roast key streams first, fast):
    thinking disabled + low effort — sampling params like temperature are
    rejected on claude-opus-5, so joke variance is prompt-driven (rubric.py).
    Refusal fallbacks are enabled on Opus/Fable models so a safety-classifier
    decline mid-demo re-runs server-side instead of breaking the overlay.
    """
    model = model or config.EVAL_MODEL
    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens or config.EVAL_MAX_TOKENS,
        "system": prompt.system,
        "messages": [{"role": "user", "content": _user_content(prompt)}],
        "thinking": {"type": "disabled"},
        "output_config": {"effort": config.EVAL_EFFORT},
    }
    if model.startswith(("claude-opus-5", "claude-fable")):
        kwargs["betas"] = ["server-side-fallback-2026-07-01"]
        kwargs["fallbacks"] = "default"

    try:
        async with _get_client().beta.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text
            final = await stream.get_final_message()
            if final.stop_reason == "refusal":
                details = getattr(final, "stop_details", None)
                category = getattr(details, "category", None) if details else None
                raise LLMError(f"model refused (category={category}) — even after fallback chain")
            if final.stop_reason == "max_tokens":
                print("[llm] warning: output truncated at max_tokens; recover_json will repair")
    except anthropic.APIError as exc:
        raise LLMError(f"evaluation model call failed: {exc}") from exc
