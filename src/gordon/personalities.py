"""Personality registry: style_note, voice_id, severity -> voice settings.

All personality prompt text lives here (and rubric.py) — nowhere else.
Voices are original synthetic ElevenLabs voices. Style notes describe generic
archetypes only — never a real, named person.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from gordon import config


@dataclass(frozen=True)
class Personality:
    id: str
    display_name: str
    style_note: str
    voice_env: str  # which config attr holds the ElevenLabs voice ID
    # severity (1..3) -> ElevenLabs voice_settings
    severity_voice_settings: dict[int, dict[str, float | bool]] = field(default_factory=dict)

    @property
    def voice_id(self) -> str:
        return getattr(config, self.voice_env, "")

    def voice_settings(self, severity: int) -> dict[str, float | bool]:
        return dict(self.severity_voice_settings.get(severity, self.severity_voice_settings[2]))


ANGRY_CHEF = Personality(
    id="angry_chef",
    display_name="Angry Chef",
    style_note=(
        "You are a furious head chef running a chaotic kitchen. The developer's prompt is a "
        "dish sent back to the pass. Roast in kitchen language: raw, undercooked, bland, "
        "slop, mise en place. Explosive, fast, clipped sentences. Ridicule the dish — the "
        "prompt and the decisions behind it — never the cook as a person."
    ),
    voice_env="VOICE_CHEF",
    severity_voice_settings={
        1: {"stability": 0.55, "similarity_boost": 0.75, "style": 0.35, "use_speaker_boost": True},
        2: {"stability": 0.40, "similarity_boost": 0.75, "style": 0.60, "use_speaker_boost": True},
        3: {"stability": 0.25, "similarity_boost": 0.75, "style": 0.85, "use_speaker_boost": True},
    },
)

DISAPPOINTED_PROFESSOR = Personality(
    id="disappointed_professor",
    display_name="Disappointed Professor",
    style_note=(
        "You are a weary tenured professor reviewing a student's submission. Quiet, slow, "
        "devastatingly dry. Long sighs implied. Grade the prompt like a failing paper: "
        "'see me after class' energy. Understatement over volume. Critique the work and "
        "the choices — never the student as a person."
    ),
    voice_env="VOICE_PROF",
    severity_voice_settings={
        1: {"stability": 0.90, "similarity_boost": 0.75, "style": 0.05, "use_speaker_boost": True},
        2: {"stability": 0.85, "similarity_boost": 0.75, "style": 0.15, "use_speaker_boost": True},
        3: {"stability": 0.75, "similarity_boost": 0.75, "style": 0.30, "use_speaker_boost": True},
    },
)

_REGISTRY: dict[str, Personality] = {p.id: p for p in (ANGRY_CHEF, DISAPPOINTED_PROFESSOR)}

DEFAULT_PERSONALITY_ID = ANGRY_CHEF.id


def get(personality_id: str) -> Personality:
    """Resolve a personality, falling back to the chef for unknown IDs."""
    return _REGISTRY.get(personality_id, _REGISTRY[DEFAULT_PERSONALITY_ID])


def all_ids() -> list[str]:
    return list(_REGISTRY)
